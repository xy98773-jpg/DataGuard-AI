"""Workflow tests: full LangGraph run over the demo dataset.

Demo data contains duplicate customer_id -> planner proposes delete_duplicate
(HIGH) -> workflow pauses for approval; tests approve to complete the run.
"""

from pathlib import Path

from app.models import CleaningPlan as PlanRow
from app.models import Execution as ExecutionRow
from app.models import Issue as IssueRow
from app.models import Validation as ValidationRow
from app.services.dataset_service import DatasetService
from app.services.workflow_service import WorkflowService
from app.storage.database import SessionLocal

DEMO_CSV = Path(__file__).resolve().parent.parent / "datasets" / "demo" / "customer.csv"


def _upload() -> str:
    svc = DatasetService()
    with open(DEMO_CSV, "rb") as f:
        info = svc.save_upload("customer.csv", f.read())
    return info.id


def _complete(dataset_id: str) -> tuple[str, dict]:
    """Start workflow and approve any pending HIGH-risk action."""
    wf = WorkflowService()
    run_id = wf.start(dataset_id, "clean customer data")
    status = wf.get_status(run_id)
    if status["status"] == "WAITING_APPROVAL":
        wf.approve(run_id)
        status = wf.get_status(run_id)
    return run_id, status


def test_full_workflow_sync_run():
    dataset_id = _upload()
    run_id, status = _complete(dataset_id)
    assert status["status"] == "SUCCESS"
    assert status["progress"] == 100


def test_workflow_persists_results():
    dataset_id = _upload()
    run_id, status = _complete(dataset_id)
    assert status["status"] == "SUCCESS"

    with SessionLocal() as session:
        issues = session.query(IssueRow).filter(IssueRow.run_id == run_id).all()
        validations = session.query(ValidationRow).filter(ValidationRow.run_id == run_id).all()
        executions = session.query(ExecutionRow).filter(ExecutionRow.run_id == run_id).all()
        plan = session.query(PlanRow).filter(PlanRow.run_id == run_id).first()

    assert len(issues) > 0
    assert any(i.issue_type == "format_error" for i in issues)
    assert len(validations) == 1
    assert validations[0].result == "PASS"
    assert plan is not None
    assert any(e.status == "success" for e in executions)


def test_workflow_produces_validation_report():
    dataset_id = _upload()
    run_id, _status = _complete(dataset_id)

    from app.storage.object_store import get_object_storage

    storage = get_object_storage()
    key = f"outputs/{dataset_id}/validation_report.json"
    assert storage.exists(key), "validation_report.json must be written to object storage"


def test_workflow_trace_events_recorded():
    dataset_id = _upload()
    run_id, _status = _complete(dataset_id)

    from app.models import TraceEvent

    with SessionLocal() as session:
        events = session.query(TraceEvent).filter(TraceEvent.run_id == run_id).all()
        types = {e.event_type for e in events}

    assert "WORKFLOW_START" in types
    assert "AGENT_DECISION" in types
    assert "HUMAN_APPROVAL" in types
    assert "VALIDATION" in types
    assert "WORKFLOW_END" in types
