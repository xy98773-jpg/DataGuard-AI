"""Dashboard API tests: platform-level stats (totals + recent runs)."""

from pathlib import Path

from app.services.dataset_service import DatasetService
from app.services.workflow_service import WorkflowService

DEMO_CSV = Path(__file__).resolve().parent.parent / "datasets" / "demo" / "customer.csv"


def _upload() -> str:
    svc = DatasetService()
    with open(DEMO_CSV, "rb") as f:
        info = svc.save_upload("customer.csv", f.read())
    return info.id


def test_dashboard_stats_shape(client):
    """stats 返回聚合指标与最近运行列表（字段完整）。"""
    resp = client.get("/api/dashboard/stats")
    assert resp.status_code == 200
    body = resp.json()
    for key in ("total_runs", "success_runs", "success_rate", "issues_found", "datasets", "recent_runs"):
        assert key in body
    assert isinstance(body["recent_runs"], list)


def test_dashboard_recent_run_has_dataset_name_and_scores(client):
    """运行一条真实流程（暂停在审批），最近运行应关联数据集名与状态。"""
    dataset_id = _upload()
    wf = WorkflowService()
    run_id = wf.start(dataset_id, "clean customer data")
    assert wf.get_status(run_id)["status"] == "WAITING_APPROVAL"

    body = client.get("/api/dashboard/stats").json()
    assert body["total_runs"] >= 1
    recent = next(r for r in body["recent_runs"] if r["run_id"] == run_id)
    assert recent["dataset_name"] == "customer.csv"
    assert recent["status"] == "WAITING_APPROVAL"
    assert recent["source_type"] == "file"
