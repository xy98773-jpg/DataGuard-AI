"""API tests: upload -> start -> poll -> results."""

from pathlib import Path

DEMO_CSV = Path(__file__).resolve().parent.parent / "datasets" / "demo" / "customer.csv"


def test_upload_dataset(client):
    with open(DEMO_CSV, "rb") as f:
        resp = client.post(
            "/api/dataset/upload",
            files={"file": ("customer.csv", f, "text/csv")},
        )
    assert resp.status_code == 200
    body = resp.json()
    assert body["dataset_id"].startswith("ds_")
    assert body["rows"] > 0


def test_full_api_flow(client):
    with open(DEMO_CSV, "rb") as f:
        resp = client.post(
            "/api/dataset/upload",
            files={"file": ("customer.csv", f, "text/csv")},
        )
    dataset_id = resp.json()["dataset_id"]

    resp = client.post("/api/workflow/start", json={"dataset_id": dataset_id})
    assert resp.status_code == 200
    run_id = resp.json()["run_id"]

    status = client.get(f"/api/workflow/{run_id}").json()
    if status["status"] == "WAITING_APPROVAL":
        client.post("/api/approval/approve", json={"run_id": run_id})
        status = client.get(f"/api/workflow/{run_id}").json()
    assert status["status"] == "SUCCESS"

    issues = client.get(f"/api/issues/{run_id}").json()
    assert len(issues["issues"]) > 0
    issue = issues["issues"][0]
    assert issue["id"].startswith("ISSUE")
    assert "confidence" in issue and "affected_rows" in issue

    plan = client.get(f"/api/plan/{run_id}").json()
    assert "actions" in plan


def test_trace_api(client):
    with open(DEMO_CSV, "rb") as f:
        resp = client.post(
            "/api/dataset/upload",
            files={"file": ("customer.csv", f, "text/csv")},
        )
    dataset_id = resp.json()["dataset_id"]
    resp = client.post("/api/workflow/start", json={"dataset_id": dataset_id})
    run_id = resp.json()["run_id"]

    trace = client.get(f"/api/trace/{run_id}").json()
    assert trace["events"], "trace events must exist"
    types = {e["event_type"] for e in trace["events"]}
    assert "WORKFLOW_START" in types
    assert "AGENT_DECISION" in types

    inspector = client.get(f"/api/trace/{run_id}?node=inspector").json()
    assert inspector["events"]
    assert all(e["node"] == "inspector" for e in inspector["events"])

    usage = client.get(f"/api/trace/{run_id}/usage").json()
    assert usage["total"] > 0
    assert "inspector" in usage["usage"]


def test_dataset_not_found(client):
    resp = client.get("/api/dataset/nonexistent")
    assert resp.status_code == 404


def _run_to_success(client) -> tuple[str, str]:
    with open(DEMO_CSV, "rb") as f:
        resp = client.post("/api/dataset/upload", files={"file": ("customer.csv", f, "text/csv")})
    dataset_id = resp.json()["dataset_id"]
    resp = client.post("/api/workflow/start", json={"dataset_id": dataset_id})
    run_id = resp.json()["run_id"]
    status = client.get(f"/api/workflow/{run_id}").json()
    if status["status"] == "WAITING_APPROVAL":
        client.post("/api/approval/approve", json={"run_id": run_id})
        status = client.get(f"/api/workflow/{run_id}").json()
    assert status["status"] == "SUCCESS"
    return dataset_id, run_id


def test_deliverables_outputs_and_download(client):
    dataset_id, _run_id = _run_to_success(client)

    outputs = client.get(f"/api/dataset/{dataset_id}/outputs").json()
    assert outputs["cleaned_exists"] is True
    assert outputs["report"] is not None
    assert outputs["report"]["run_id"]
    assert outputs["report"]["validation"]["status"] == "PASS"

    resp = client.get(f"/api/dataset/{dataset_id}/cleaned.csv")
    assert resp.status_code == 200
    assert "customer_id" in resp.text
    assert "attachment" in resp.headers.get("content-disposition", "")


def test_all_issues_api(client):
    _dataset_id, _run_id = _run_to_success(client)

    resp = client.get("/api/issues").json()
    assert len(resp["issues"]) > 0
    first = resp["issues"][0]
    assert "type" in first and "severity" in first and "affected_rows" in first

    high = client.get("/api/issues?severity=HIGH").json()
    assert high["issues"] and all(i["severity"] == "HIGH" for i in high["issues"])
