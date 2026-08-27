"""Web Data Source API: single / batch URL registration."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.web_service import WebSourceService

router = APIRouter(tags=["web"])
_svc = WebSourceService()


class UrlRequest(BaseModel):
    url: str


class BatchRequest(BaseModel):
    urls: list[str]


@router.post("/web/register")
def register(req: UrlRequest) -> dict:
    try:
        info = _svc.register(req.url)
    except Exception as exc:  # noqa: BLE001 - surface fetch/parse errors
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "dataset_id": info.id,
        "filename": info.filename,
        "rows": info.row_count,
        "source_type": info.source_type,
    }


@router.post("/web/register_batch")
def register_batch(req: BatchRequest) -> dict:
    infos = _svc.register_batch(req.urls)
    return {
        "registered": [
            {"dataset_id": i.id, "filename": i.filename, "rows": i.row_count}
            for i in infos
        ],
        "count": len(infos),
    }
