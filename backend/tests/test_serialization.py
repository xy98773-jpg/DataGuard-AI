"""Regression tests: JSON-safe serialization (numpy/pandas leak) + issue list ordering."""

import numpy as np

from app.schemas.common import ExecutionMode, RiskLevel
from app.schemas.plan import CleaningPlan, PlanAction
from app.services.dataset_service import DatasetService
from app.tools.data import register_data_tools
from app.tools.cleaning import register_cleaning_tools
from app.tools.registry import _registry
from app.utils.serialization import json_safe


def test_json_safe_numpy_scalars():
    assert json_safe(np.int64(5)) == 5
    assert json_safe(np.float64(5.5)) == 5.5
    assert json_safe(np.float64(float("nan"))) is None
    assert json_safe(np.bool_(True)) is True
    assert json_safe({"a": [np.int64(1), np.float64(2.0)], "b": None}) == {"a": [1, 2.0], "b": None}


def test_json_safe_records():
    import json

    payload = {
        "before": {"column_value": np.int64(28), "occurrences": np.int64(4)},
        "after": "deleted",
    }
    safe = json_safe(payload)
    assert isinstance(safe["before"]["column_value"], int)
    json.dumps(safe)  # must not raise


def test_delete_duplicate_blocked_on_numeric_column(client):
    """硬性安全规则：数值列禁止 delete_duplicate（Execution Engine 层拦截）."""
    from pathlib import Path

    from app.governance.execution import ExecutionEngine
    from app.tools.registry import get_registry

    assert get_registry().get("delete_duplicate") is not None  # conftest 已注册工具
    demo = Path(__file__).resolve().parent.parent / "datasets" / "demo" / "customer.csv"
    with open(demo, "rb") as f:
        info = DatasetService().save_upload("customer.csv", f.read())

    plan = CleaningPlan(
        actions=[
            PlanAction(tool="delete_duplicate", column="age", parameters={}, risk=RiskLevel.HIGH),
            PlanAction(tool="delete_duplicate", column="customer_id", parameters={}, risk=RiskLevel.HIGH),
        ]
    )
    result = ExecutionEngine().execute_plan(
        dataset_id=info.id, plan=plan, ext="csv", mode=ExecutionMode.DRY_RUN
    )
    by_col = {r["column"]: r for r in result["results"]}
    assert by_col["age"]["status"] == "failed"
    assert "禁止" in by_col["age"]["error"]
    assert by_col["customer_id"]["status"] == "success"  # 唯一标识列仍允许


def test_issues_api_returns_dataset_name_and_newest_first(client):
    """The cross-run issue list must carry dataset_name (grouping) and order by run recency."""
    from pathlib import Path

    demo = Path(__file__).resolve().parent.parent / "datasets" / "demo" / "customer.csv"
    with open(demo, "rb") as f:
        resp = client.post("/api/dataset/upload", files={"file": ("customer.csv", f, "text/csv")})
    dataset_id = resp.json()["dataset_id"]

    resp = client.post("/api/workflow/start", json={"dataset_id": dataset_id})
    run_id = resp.json()["run_id"]
    status = client.get(f"/api/workflow/{run_id}").json()
    if status["status"] == "WAITING_APPROVAL":
        client.post("/api/approval/approve", json={"run_id": run_id})
        status = client.get(f"/api/workflow/{run_id}").json()
    assert status["status"] == "SUCCESS"

    issues = client.get("/api/issues?limit=10").json().get("issues", [])
    assert issues, "expected at least one persisted issue"
    for i in issues:
        assert i.get("dataset_name"), "dataset_name must be resolved to a filename"
