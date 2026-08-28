"""任务并发与取消测试：并发限制 / 取消状态 / 运行列表."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services import workflow_service as ws
from app.storage.database import SessionLocal
from app.models import WorkflowRun

client = TestClient(app)


@pytest.fixture(autouse=True)
def _reset_concurrency_state():
    """每个测试前后重置并发控制状态，防止互相干扰."""
    with ws._active_runs_lock:
        ws._active_runs.clear()
        ws._cancel_flags.clear()
    # 清理测试库中残留的非终态 run（其他测试启动的 workflow 会留下 RUNNING/WAITING_APPROVAL 记录）
    with SessionLocal() as session:
        session.query(WorkflowRun).filter(WorkflowRun.status.in_(["PENDING", "RUNNING", "WAITING_APPROVAL"])).update({"status": "CANCELLED"})
        session.commit()
    yield


def _create_test_dataset():
    """辅助函数：上传一个测试数据集."""
    demo = Path(__file__).resolve().parent.parent / "datasets" / "demo" / "customer.csv"
    with open(demo, "rb") as f:
        resp = client.post(
            "/api/dataset/upload",
            files={"file": ("cancel_test.csv", f, "text/csv")},
            data={"name": "并发取消测试集"},
        )
    return resp.json()["dataset_id"]


def test_active_runs_empty(auth_headers):
    """无任务时返回空列表."""
    resp = client.get("/api/workflow/active", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["runs"] == []


def test_cancel_nonexistent(auth_headers):
    """取消不存在的任务 -> 400."""
    resp = client.post("/api/workflow/run_fake_123/cancel", headers=auth_headers)
    assert resp.status_code == 400
    assert "无法取消" in resp.json()["detail"]


def test_cancel_and_verify_status(auth_headers):
    """上传 -> 启动 -> 取消 -> 验证状态."""
    ds_id = _create_test_dataset()
    resp = client.post("/api/workflow/start", json={"dataset_id": ds_id}, headers=auth_headers)
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    # 立即取消
    resp = client.post(f"/api/workflow/{run_id}/cancel", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["status"] == "cancelled"

    # 检查运行列表（取消操作会从活跃集合移除）
    active_resp = client.get("/api/workflow/active", headers=auth_headers)
    assert not any(r["run_id"] == run_id for r in active_resp.json()["runs"])


def test_concurrency_limit_rejects(auth_headers):
    """并发达到上限时拒绝新任务 (429)."""
    # 模拟已满（直接向活跃集合添加 3 个假 ID）
    with ws._active_runs_lock:
        ws._active_runs.update({"run_1", "run_2", "run_3"})
        assert len(ws._active_runs) == 3

    ds_id = _create_test_dataset()
    # 尝试启动新任务
    resp = client.post("/api/workflow/start", json={"dataset_id": ds_id}, headers=auth_headers)
    assert resp.status_code == 429
    assert "最大并发" in resp.json()["detail"]

    # 清理
    with ws._active_runs_lock:
        ws._active_runs.clear()
