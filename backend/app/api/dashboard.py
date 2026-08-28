"""Dashboard API: 平台级统计（提示词三十六 Dashboard 页面数据源）。

- GET /api/dashboard/stats -> 总运行数 / 成功率 / 发现问题数 / 数据集数 + 最近运行列表（关联数据集名与质量分）

统计全部来自真实业务库（workflow_runs / issues / datasets / validations）。
"""

from fastapi import APIRouter
from sqlalchemy import func

from app.models import Dataset, Issue, Validation, WorkflowRun
from app.storage.database import SessionLocal

router = APIRouter(tags=["dashboard"])


@router.get("/dashboard/stats")
def get_dashboard_stats() -> dict:
    """平台级统计：聚合指标 + 最近运行列表（含数据源类型与治理前后质量分）。"""
    with SessionLocal() as session:
        total_runs = session.query(func.count(WorkflowRun.id)).scalar() or 0
        succeeded = (
            session.query(func.count(WorkflowRun.id))
            .filter(WorkflowRun.status == "SUCCESS")
            .scalar()
            or 0
        )
        issues_found = session.query(func.count(Issue.id)).scalar() or 0
        datasets = session.query(func.count(Dataset.id)).scalar() or 0

        # 最近运行：关联数据集（取显示名，回退文件名）+ 质量分（每个 run 由 _persist 保证最多一条最新 validation）
        recent = (
            session.query(WorkflowRun, Dataset, Validation)
            .join(Dataset, WorkflowRun.dataset_id == Dataset.id)
            .outerjoin(Validation, Validation.run_id == WorkflowRun.id)
            .order_by(WorkflowRun.created_at.desc())
            .limit(10)
            .all()
        )

    return {
        "total_runs": total_runs,
        "success_runs": succeeded,
        "success_rate": round(succeeded / total_runs * 100, 1) if total_runs else 0.0,
        "issues_found": issues_found,
        "datasets": datasets,
        "quality_trend": [
            {
                "run_id": run.id,
                "dataset_name": ds.name or ds.filename,
                "created_at": run.created_at.isoformat() if run.created_at else "",
                "before_score": round(val.before_score, 2) if val else None,
                "after_score": round(val.after_score, 2) if val else None,
            }
            for run, ds, val in recent
            if val and val.before_score and val.after_score
        ],
        "recent_runs": [
            {
                "run_id": run.id,
                "dataset_name": ds.name or ds.filename,
                "filename": ds.filename,
                "source_type": ds.source_type,  # file | web | database
                "status": run.status,  # SUCCESS / FAILED / WAITING_APPROVAL / RUNNING / PENDING
                "iteration": run.iteration,  # 重规划次数（>0 说明经历过反思重规划）
                "created_at": run.created_at.isoformat() if run.created_at else "",
                "before_score": val.before_score if val else None,
                "after_score": val.after_score if val else None,
            }
            for run, ds, val in recent
        ],
    }
