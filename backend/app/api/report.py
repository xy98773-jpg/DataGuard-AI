"""报告 API：导出治理报告（HTML / PDF）。"""

from fastapi import APIRouter, HTTPException, Response
from fastapi.responses import HTMLResponse

from app.services.report_service import build_run_report, render_html, render_pdf

router = APIRouter(tags=["report"])


def _load_report(run_id: str) -> dict:
    try:
        return build_run_report(run_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/report/{run_id}/html")
def get_report_html(run_id: str) -> HTMLResponse:
    """返回自包含 HTML 报告（可直接浏览器打开 / 另存）。"""
    r = _load_report(run_id)
    return HTMLResponse(render_html(r))


@router.get("/report/{run_id}/pdf")
def get_report_pdf(run_id: str) -> Response:
    """返回 PDF 报告（系统 Edge 无头打印渲染）。"""
    r = _load_report(run_id)
    try:
        pdf = render_pdf(render_html(r))
    except RuntimeError as e:
        raise HTTPException(status_code=500, detail=str(e))
    fname = f"{r['dataset_name']}_治理报告.pdf"
    from urllib.parse import quote

    # header 只允许 latin-1：中文名走 RFC 5987 filename*，ASCII 兜底
    disposition = f"attachment; filename=\"report.pdf\"; filename*=UTF-8''{quote(fname)}"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": disposition},
    )
