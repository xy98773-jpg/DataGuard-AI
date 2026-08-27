"""Workflow tests: supervisor routing + reflection / re-plan limits."""

from pathlib import Path

from app.agents import PlannerAgent
from app.graph import nodes
from app.llm.client import LLMUsage
from app.schemas.plan import CleaningPlan, PlanAction
from app.services.dataset_service import DatasetService
from app.services.workflow_service import WorkflowService

DEMO_CSV = Path(__file__).resolve().parent.parent / "datasets" / "demo" / "customer.csv"


class BadPlannerAgent(PlannerAgent):
    """Always proposes an unregistered tool -> plan_validator rejects it."""

    def run(self, issues, context=None):
        return (
            CleaningPlan(actions=[PlanAction(tool="nonexistent_tool", column="phone", issue_id="ISSUE001")]),
            LLMUsage(),
        )


def _upload() -> str:
    svc = DatasetService()
    with open(DEMO_CSV, "rb") as f:
        info = svc.save_upload("customer.csv", f.read())
    return info.id


def test_full_workflow_has_supervisor_route():
    dataset_id = _upload()
    wf = WorkflowService()
    run_id = wf.start(dataset_id, "clean customer data")
    status = wf.get_status(run_id)
    if status["status"] == "WAITING_APPROVAL":  # HIGH-risk action -> approve
        wf.approve(run_id)
        status = wf.get_status(run_id)
    assert status["status"] == "SUCCESS"
    assert "supervisor" in status["nodes"]
    assert "approval" in status["nodes"]
    # demo dataset: plan passes validation, LOW risk auto-executes
    assert status["progress"] == 100


def test_replan_reaches_max_iteration(monkeypatch):
    monkeypatch.setattr(nodes, "_planner_factory", lambda: BadPlannerAgent())
    dataset_id = _upload()
    wf = WorkflowService()
    run_id = wf.start(dataset_id, "clean customer data")
    status = wf.get_status(run_id)
    assert status["status"] == "FAILED"  # unrecoverable plan -> max re-plans
    assert status["iteration"] == 3  # MAX_ITERATION reached


def test_conditional_route_plan_validator_to_replanner(monkeypatch):
    """plan_validator FAIL must route back to planner (not crash the graph)."""
    monkeypatch.setattr(nodes, "_planner_factory", lambda: BadPlannerAgent())
    dataset_id = _upload()
    wf = WorkflowService()
    run_id = wf.start(dataset_id, "clean customer data")
    status = wf.get_status(run_id)
    assert status["status"] in ("SUCCESS", "FAILED")
    assert status["iteration"] >= 1
