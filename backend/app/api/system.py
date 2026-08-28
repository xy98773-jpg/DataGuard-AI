"""System stats API: 可观测性指标（运行统计 + LLM 缓存命中统计）。"""

from fastapi import APIRouter
from sqlalchemy import func

from app.llm.providers import cache_stats
from app.models import Dataset, Issue, TraceEvent, WorkflowRun
from app.storage.database import SessionLocal

router = APIRouter(tags=["system"])


@router.get("/system/stats")
def get_system_stats() -> dict:
    """平台可观测性指标：运行统计 + 平均耗时 + LLM 缓存命中。"""
    with SessionLocal() as session:
        total_runs = (
            session.query(func.count(WorkflowRun.id))
            .filter(WorkflowRun.status != "CANCELLED")
            .scalar()
            or 0
        )
        succeeded = (
            session.query(func.count(WorkflowRun.id))
            .filter(WorkflowRun.status == "SUCCESS")
            .scalar()
            or 0
        )
        issues_found = session.query(func.count(Issue.id)).scalar() or 0
        datasets = session.query(func.count(Dataset.id)).scalar() or 0

        # 平均运行耗时：按 run 聚合 trace_events.latency 总和，再取平均（仅成功/失败 run）
        rows = (
            session.query(
                WorkflowRun.id,
                func.sum(TraceEvent.latency),
            )
            .join(TraceEvent, TraceEvent.run_id == WorkflowRun.id)
            .filter(WorkflowRun.status.in_(["SUCCESS", "FAILED"]))
            .group_by(WorkflowRun.id)
            .all()
        )
        run_times = [t for _, t in rows if t is not None]
        avg_run_seconds = round(sum(run_times) / len(run_times), 1) if run_times else 0.0

    return {
        "total_runs": total_runs,
        "success_runs": succeeded,
        "success_rate": round(succeeded / total_runs * 100, 1) if total_runs else 0.0,
        "issues_found": issues_found,
        "datasets": datasets,
        "avg_run_seconds": avg_run_seconds,
        "cache": cache_stats(),
    }
