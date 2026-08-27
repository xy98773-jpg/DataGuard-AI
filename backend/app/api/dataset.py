"""Dataset API: upload / detail / list / outputs."""

import json

from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile

from app.models import Dataset
from app.services.dataset_service import DatasetService
from app.storage.database import SessionLocal
from app.storage.object_store import get_object_storage

router = APIRouter(tags=["dataset"])
_svc = DatasetService()


@router.get("/dataset/{dataset_id}/outputs")
def get_outputs(dataset_id: str) -> dict:
    """治理交付物：cleaned.csv 是否存在 + validation_report.json 内容."""
    storage = get_object_storage()
    cleaned_key = f"outputs/{dataset_id}/cleaned.csv"
    report_key = f"outputs/{dataset_id}/validation_report.json"
    result: dict = {"dataset_id": dataset_id, "cleaned_exists": storage.exists(cleaned_key)}
    if storage.exists(report_key):
        try:
            result["report"] = json.loads(storage.load(report_key).decode("utf-8"))
        except Exception:  # noqa: BLE001
            result["report"] = None
    else:
        result["report"] = None
    return result


@router.get("/dataset/{dataset_id}/cleaned.csv")
def download_cleaned(dataset_id: str) -> Response:
    """下载清洗后的新数据（最终交付物）."""
    storage = get_object_storage()
    key = f"outputs/{dataset_id}/cleaned.csv"
    if not storage.exists(key):
        raise HTTPException(status_code=404, detail="cleaned.csv 不存在（该运行可能未进入 EXECUTE 阶段）")
    data = storage.load(key)
    return Response(
        content=data,
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{dataset_id}_cleaned.csv"'},
    )


@router.get("/dataset/list")
def list_datasets(limit: int = 10) -> dict:
    with SessionLocal() as session:
        rows = (
            session.query(Dataset)
            .order_by(Dataset.created_at.desc())
            .limit(min(max(limit, 1), 50))
            .all()
        )
        return {
            "datasets": [
                {
                    "id": r.id,
                    "filename": r.filename,
                    "source_type": r.source_type,
                    "row_count": r.row_count,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                }
                for r in rows
            ]
        }


@router.post("/dataset/upload")
async def upload_dataset(file: UploadFile = File(...), name: str | None = Form(default=None)) -> dict:
    content = await file.read()
    try:
        info = _svc.save_upload(file.filename or "upload.csv", content, name=name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {
        "dataset_id": info.id,
        "filename": info.filename,
        "name": info.name,
        "rows": info.row_count,
        "columns": info.column_count,
    }


@router.get("/dataset/{dataset_id}")
def get_dataset(dataset_id: str) -> dict:
    info = _svc.get_info(dataset_id)
    if info is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return info.model_dump()
