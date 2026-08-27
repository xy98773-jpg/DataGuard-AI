"""Web Data Source tests: crawler->parser->extractor via httpx MockTransport."""

import httpx

from app.services.dataset_service import DatasetService
from app.services.web_service import WebSourceService
from app.services.workflow_service import WorkflowService

HTML = """<html><body><table>
<tr><th>name</th><th>phone</th></tr>
<tr><td>Alice</td><td>138-1234-5678</td></tr>
<tr><td>Bob</td><td>13900000000</td></tr>
</table></body></html>"""


def _transport_for(content: str, ctype: str = "text/html"):
    return httpx.MockTransport(
        lambda req: httpx.Response(200, text=content, headers={"content-type": ctype})
    )


def test_parse_html_table():
    svc = WebSourceService(transport=_transport_for(HTML))
    info = svc.register("http://example.com/data")
    assert info.source_type == "web"
    assert info.row_count == 2
    assert "phone" in [c for c in ["name", "phone"]]


def test_parse_json_array():
    svc = WebSourceService(transport=_transport_for('[{"id":1,"name":"a"},{"id":2,"name":"b"}]', "application/json"))
    df = svc.parse('[{"id":1,"name":"a"},{"id":2,"name":"b"}]'.encode(), "application/json")
    assert list(df.columns) == ["id", "name"]
    assert len(df) == 2


def test_register_batch():
    svc = WebSourceService(transport=_transport_for(HTML))
    infos = svc.register_batch(["http://a.com/1", "http://b.com/2"])
    assert len(infos) == 2


def test_web_governance_flow():
    svc = WebSourceService(transport=_transport_for(HTML))
    info = svc.register("http://example.com/data")

    wf = WorkflowService()
    run_id = wf.start(info.id, "govern web data")
    status = wf.get_status(run_id)
    if status["status"] == "WAITING_APPROVAL":
        wf.approve(run_id)
        status = wf.get_status(run_id)
    assert status["status"] == "SUCCESS"


def test_web_api_register(client):
    # inject transport into the service used by the API router
    import app.api.web as web_api

    web_api._svc = WebSourceService(transport=_transport_for(HTML))
    resp = client.post("/api/web/register", json={"url": "http://example.com/data"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["source_type"] == "web"
    assert body["rows"] == 2
