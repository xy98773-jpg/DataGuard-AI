"""Approval tests: human-in-the-loop pause/resume/reject."""

from pathlib import Path

from app.services.dataset_service import DatasetService
from app.services.workflow_service import WorkflowService

DEMO_CSV = Path(__file__).resolve().parent.parent / "datasets" / "demo" / "customer.csv"


def _upload() -> str:
    svc = DatasetService()
    with open(DEMO_CSV, "rb") as f:
        info = svc.save_upload("customer.csv", f.read())
    return info.id


def test_workflow_pauses_for_approval():
    dataset_id = _upload()
    wf = WorkflowService()
    run_id = wf.start(dataset_id, "clean customer data")
    status = wf.get_status(run_id)
    assert status["status"] == "WAITING_APPROVAL"
    assert status["current_node"] == "approval"

    pending = wf.get_pending_approvals()
    assert any(a["run_id"] == run_id for a in pending)
    approval = next(a for a in pending if a["run_id"] == run_id and a["operation"]["tool"] == "delete_duplicate")
    assert approval["operation"]["risk"] == "HIGH"
    assert approval["operation"]["affected_rows"] >= 4


def test_issues_persisted_while_paused():
    """切换页面/刷新后仍能恢复：审批暂停时 issues/plan 必须已持久化."""
    from app.models import CleaningPlan as PlanRow
    from app.models import Issue as IssueRow
    from app.storage.database import SessionLocal

    dataset_id = _upload()
    wf = WorkflowService()
    run_id = wf.start(dataset_id, "clean customer data")
    assert wf.get_status(run_id)["status"] == "WAITING_APPROVAL"

    with SessionLocal() as session:
        issues = session.query(IssueRow).filter(IssueRow.run_id == run_id).all()
        plan = session.query(PlanRow).filter(PlanRow.run_id == run_id).first()
    assert len(issues) > 0, "issues must be persisted while the run is paused"
    assert plan is not None and plan.plan.get("actions"), "plan must be persisted while paused"


def test_approve_resumes_and_succeeds():
    dataset_id = _upload()
    wf = WorkflowService()
    run_id = wf.start(dataset_id, "clean customer data")
    assert wf.get_status(run_id)["status"] == "WAITING_APPROVAL"

    result = wf.approve(run_id, operator="tester")
    assert result["status"] == "SUCCESS"
    assert wf.get_status(run_id)["status"] == "SUCCESS"


def test_reject_ends_run():
    dataset_id = _upload()
    wf = WorkflowService()
    run_id = wf.start(dataset_id, "clean customer data")
    assert wf.get_status(run_id)["status"] == "WAITING_APPROVAL"

    result = wf.reject(run_id, operator="tester")
    assert result["status"] == "FAILED"  # rejected -> run terminated
    assert wf.get_status(run_id)["status"] == "FAILED"


def test_save_pending_approvals_idempotent():
    """同一 run 多次暂停时，_save_pending_approvals 只保留最新一批 PENDING（旧行清理，不累积重复）."""
    from app.models import Approval as ApprovalRow
    from app.storage.database import SessionLocal

    run_id = "run_idem_test"
    payload1 = {"approval_requests": [
        {"id": "delete_duplicate__customer_id", "tool": "delete_duplicate", "column": "customer_id", "affected_rows": 4, "risk": "HIGH"},
        {"id": "fill_missing__email", "tool": "fill_missing", "column": "email", "affected_rows": 2, "risk": "MEDIUM"},
    ]}
    payload2 = {"approval_requests": [
        {"id": "normalize_phone__phone", "tool": "normalize_phone", "column": "phone", "affected_rows": 8, "risk": "LOW"},
    ]}

    # 第一次暂停：插入 2 条
    WorkflowService._save_pending_approvals(run_id, payload1)
    with SessionLocal() as session:
        n1 = session.query(ApprovalRow).filter(ApprovalRow.run_id == run_id, ApprovalRow.status == "PENDING").count()
    assert n1 == 2

    # 第二次暂停：旧 PENDING 清理，只保留新的 1 条
    WorkflowService._save_pending_approvals(run_id, payload2)
    with SessionLocal() as session:
        pending = session.query(ApprovalRow).filter(ApprovalRow.run_id == run_id, ApprovalRow.status == "PENDING").all()
        assert len(pending) == 1
        op = __import__("json").loads(pending[0].operation)
        assert op["id"] == "normalize_phone__phone"


def test_submit_partial_decisions_rejects_some():
    """逐条审批：部分批准 + 部分拒绝时，被拒绝的操作不得执行."""
    from app.models import Execution as ExecutionRow
    from app.storage.database import SessionLocal

    dataset_id = _upload()
    wf = WorkflowService()
    run_id = wf.start(dataset_id, "clean customer data")
    assert wf.get_status(run_id)["status"] == "WAITING_APPROVAL"

    pending = [a for a in wf.get_pending_approvals() if a["run_id"] == run_id]
    assert len(pending) >= 2, "expected at least two approval requests"
    decisions = {}
    for i, a in enumerate(pending):
        op = a["operation"]
        op_id = op.get("id") or f"{op['tool']}__{op['column']}"
        decisions[op_id] = "approve" if i == 0 else "reject"

    result = wf.submit_decisions(run_id, decisions, operator="tester")
    assert result["status"] == "SUCCESS"

    with SessionLocal() as session:
        executed = [r.tool_name for r in session.query(ExecutionRow).filter(ExecutionRow.run_id == run_id).all()]
    approved_tool = pending[0]["operation"]["tool"]
    assert approved_tool in executed, "approved operation must be executed"
    for a in pending[1:]:
        assert a["operation"]["tool"] not in executed, "rejected operation must NOT be executed"


def test_approval_api_flow(client):
    with open(DEMO_CSV, "rb") as f:
        resp = client.post("/api/dataset/upload", files={"file": ("customer.csv", f, "text/csv")})
    dataset_id = resp.json()["dataset_id"]

    resp = client.post("/api/workflow/start", json={"dataset_id": dataset_id})
    run_id = resp.json()["run_id"]

    pending = client.get("/api/approval/pending").json()
    assert any(a["run_id"] == run_id for a in pending["approvals"])

    resp = client.post("/api/approval/approve", json={"run_id": run_id, "operator": "tester"})
    assert resp.status_code == 200
    status = client.get(f"/api/workflow/{run_id}").json()
    assert status["status"] == "SUCCESS"
