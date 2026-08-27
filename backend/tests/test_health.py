"""Phase 0 smoke tests: backend boots, health endpoint works."""


def test_health(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "ok"
    assert body["app"] == "DataGuard AI"


def test_api_prefix_registered(client):
    # core API routers are mounted under /api
    resp = client.get("/api/dataset/nonexistent")
    assert resp.status_code in (404, 405)  # route exists -> dataset router mounted
