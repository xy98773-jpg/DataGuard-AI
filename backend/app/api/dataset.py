"""Dataset API: upload / detail / list / outputs."""

import json

from fastapi import APIRouter, File, Form, HTTPException, Query, Response, UploadFile
from sqlalchemy import func

from app.models import Dataset, Issue as IssueRow, WorkflowRun
from app.services.dataset_service import DatasetService
from app.storage.database import SessionLocal
from app.storage.object_store import get_object_storage

router = APIRouter(tags=["dataset"])
_svc = DatasetService()


@router.get("/dataset/{dataset_id}/outputs")
def get_outputs(dataset_id: str) -> dict:
    """治理交付物：cleaned.csv 是否存在 + validation_report.json 内容.

    对 database 源：交付物是**影子表**（execution 记录中 tool=shadow_table 的项），
    返回 shadow_table / shadow_rows，cleaned_exists 置 True（影子表即交付物）。
    """
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
    # Shadow Table（database 源交付物）：从执行记录提取影子表信息
    report = result.get("report") or {}
    shadow_item = next(
        (e for e in report.get("execution", []) if e.get("tool") == "shadow_table"),
        None,
    )
    if shadow_item:
        result["shadow_table"] = shadow_item.get("shadow_table", "")
        result["shadow_rows"] = shadow_item.get("affected_rows", 0)
        result["cleaned_exists"] = True  # 影子表即 database 源的治理交付物
    return result


@router.get("/dataset/{dataset_id}/latest-run")
def get_latest_run(dataset_id: str) -> dict:
    """返回该数据集最近一次治理运行（前端恢复工作台用）。"""
    with SessionLocal() as session:
        run = (
            session.query(WorkflowRun)
            .filter(WorkflowRun.dataset_id == dataset_id)
            .order_by(WorkflowRun.created_at.desc())
            .first()
        )
    if not run:
        return {"dataset_id": dataset_id, "run_id": "", "status": ""}
    return {"dataset_id": dataset_id, "run_id": run.id, "status": run.status}


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
def list_datasets(
    limit: int = 10,
    offset: int = 0,
    search: str | None = Query(default=None),
    source_type: str | None = Query(default=None),
) -> dict:
    """数据集列表（首页/工作台管理用）.

    每行含：显示名（name，上传时自定义）/ 文件名 / 来源类型 / 行列数 /
    最近一次治理状态（该数据集最新 run 的 status）/ 问题总数（跨运行 issues 计数）。
    支持 search（按显示名/文件名模糊）、source_type 筛选、limit/offset 分页——
    数据集多了之后也能快速定位与治理。
    """
    with SessionLocal() as session:
        q = session.query(Dataset)
        if search:
            like = f"%{search}%"
            q = q.filter((Dataset.name.like(like)) | (Dataset.filename.like(like)))
        if source_type:
            q = q.filter(Dataset.source_type == source_type)
        total = q.count()
        rows = (
            q.order_by(Dataset.created_at.desc())
            .offset(max(offset, 0))
            .limit(min(max(limit, 1), 50))
            .all()
        )

        ds_ids = [r.id for r in rows]
        # 每个数据集的最新一次运行状态（created_at 最大者）
        run_status: dict[str, str] = {}
        if ds_ids:
            for run_id, ds_id, status in (
                session.query(WorkflowRun.id, WorkflowRun.dataset_id, WorkflowRun.status)
                .filter(WorkflowRun.dataset_id.in_(ds_ids))
                .all()
            ):
                # 后查询到的（较新）覆盖旧值，等价于取最新 run 的状态
                run_status[ds_id] = status
        # 每个数据集的问题总数（跨运行）
        issue_counts: dict[str, int] = {}
        if ds_ids:
            for ds_id, n in (
                session.query(WorkflowRun.dataset_id, func.count(IssueRow.id))
                .join(IssueRow, IssueRow.run_id == WorkflowRun.id)
                .filter(WorkflowRun.dataset_id.in_(ds_ids))
                .group_by(WorkflowRun.dataset_id)
                .all()
            ):
                issue_counts[ds_id] = int(n)

        return {
            "total": total,
            "datasets": [
                {
                    "id": r.id,
                    "name": r.name or r.filename,
                    "filename": r.filename,
                    "source_type": r.source_type,
                    "row_count": r.row_count,
                    "column_count": r.column_count,
                    "created_at": r.created_at.isoformat() if r.created_at else "",
                    "last_status": run_status.get(r.id, ""),  # SUCCESS/FAILED/WAITING_APPROVAL/RUNNING...
                    "issue_count": issue_counts.get(r.id, 0),
                }
                for r in rows
            ],
        }


@router.patch("/dataset/{dataset_id}")
def rename_dataset(dataset_id: str, body: dict) -> dict:
    """事后改名：更新数据集显示名（首页/工作台/问题中心立即生效）."""
    name = (body or {}).get("name", "")
    try:
        info = _svc.rename(dataset_id, name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if info is None:
        raise HTTPException(status_code=404, detail="dataset not found")
    return {
        "dataset_id": info.id,
        "filename": info.filename,
        "name": info.name,
    }


@router.delete("/dataset/{dataset_id}")
def delete_dataset(dataset_id: str) -> dict:
    """删除数据集：数据库记录 + 文件 + 该数据集全部运行历史（破坏性操作，前端需二次确认）."""
    deleted = _svc.delete_dataset(dataset_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="dataset not found")
    return {"dataset_id": dataset_id, "deleted": True}


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
