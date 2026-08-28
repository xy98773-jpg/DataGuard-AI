"""报告服务测试：聚合 / HTML / PDF / API 端点。"""

import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.report_service import build_run_report, render_html, render_pdf

client = TestClient(app)


def _make_run(client, name="报告测试数据集"):
    """上传 CSV 并跑一次治理，返回 run_id（跳过审批风险：全拒绝也行，有数据即可）。"""
    demo = Path(__file__).resolve().parent.parent / "datasets" / "demo" / "all_issues.csv"
    with open(demo, "rb") as f:
        r = client.post(
            "/api/dataset/upload",
            files={"file": ("all_issues.csv", f, "text/csv")},
            data={"name": name},
        )
    ds_id = r.json()["dataset_id"]
    run = client.post("/api/workflow/start", json={"dataset_id": ds_id})
    run_id = run.json().get("run_id") or run.json().get("id")
    # 若停在审批，直接拒绝全部 → 结束（报告聚合不依赖最终成功）
    if run_id and client.get(f"/api/workflow/{run_id}").json().get("status") == "WAITING_APPROVAL":
        client.post("/api/approval/submit", json={"run_id": run_id, "operator": "tester", "decisions": []})
    return run_id


@pytest.fixture(scope="module")
def run_id():
    return _make_run(client)


def test_build_report_aggregates(run_id):
    r = build_run_report(run_id)
    s = r["summary"]
    assert s["issues_total"] > 0
    assert r["dataset_name"] == "报告测试数据集"
    assert r["status_zh"] in ("成功", "失败", "待审批", "运行中", "待开始")
    assert s["before_score"] is not None and s["after_score"] is not None
    # 严重级别分布总和 = 问题总数
    assert sum(x["count"] for x in r["severity_dist"]) == s["issues_total"]
    # 执行/审批列表存在
    assert isinstance(r["executions"], list)
    assert isinstance(r["approvals"], list)


def test_render_html_contains_key_sections(run_id):
    html = render_html(build_run_report(run_id))
    assert "数据治理报告" in html
    assert "质量维度得分" in html
    assert "问题分布" in html
    assert "清洗计划" in html
    assert "执行明细与样本对比" in html
    assert "审批记录" in html
    assert "问题明细" in html


def test_render_pdf_is_valid(run_id):
    pdf = render_pdf(render_html(build_run_report(run_id)))
    assert pdf[:5] == b"%PDF-"
    assert len(pdf) > 5000


def test_report_api_html(run_id):
    resp = client.get(f"/api/report/{run_id}/html")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "数据治理报告" in resp.text


def test_report_api_pdf(run_id):
    resp = client.get(f"/api/report/{run_id}/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:5] == b"%PDF-"
    # 中文文件名走 RFC 5987
    assert "filename*=UTF-8''" in resp.headers["content-disposition"]


def test_report_api_404():
    assert client.get("/api/report/run_nope/html").status_code == 404
    assert client.get("/api/report/run_nope/pdf").status_code == 404
