"""Workflow API: start / status / issues / plan / validation."""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.models import CleaningPlan as PlanRow
from app.models import Dataset as DatasetRow
from app.models import Issue as IssueRow
from app.models import Validation as ValidationRow
from app.models import WorkflowRun
from app.services.workflow_service import WorkflowService
from app.storage.database import SessionLocal

router = APIRouter(tags=["workflow"])
_svc = WorkflowService()


class StartRequest(BaseModel):
    dataset_id: str
    goal: str = Field(default="clean customer data")


@router.post("/workflow/start")
def start_workflow(req: StartRequest) -> dict:
    try:
        run_id = _svc.start(req.dataset_id, req.goal)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"run_id": run_id, "status": "running"}


@router.get("/workflow/{run_id}")
def get_workflow(run_id: str) -> dict:
    return _svc.get_status(run_id)


@router.get("/issues")
def list_all_issues(
    severity: str | None = Query(default=None),
    issue_type: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=500),
) -> dict:
    """跨运行的问题列表（Issue Explorer 页数据源）."""
    with SessionLocal() as session:
        q = (
            session.query(IssueRow, WorkflowRun.dataset_id, DatasetRow.filename, DatasetRow.name)
            .join(WorkflowRun, IssueRow.run_id == WorkflowRun.id)
            .join(DatasetRow, WorkflowRun.dataset_id == DatasetRow.id, isouter=True)
        )
        if severity:
            q = q.filter(IssueRow.severity == severity)
        if issue_type:
            q = q.filter(IssueRow.issue_type == issue_type)
        rows = q.order_by(WorkflowRun.created_at.desc(), IssueRow.id.desc()).limit(limit).all()
        return {
            "issues": [
                {
                    "id": issue.agent_issue_id or issue.id,
                    "run_id": issue.run_id,
                    "dataset_id": dataset_id,
                    "dataset_name": (name or filename) or dataset_id,
                    "dataset_file": filename or dataset_id,
                    "type": issue.issue_type,
                    "column": issue.column_name,
                    "severity": issue.severity,
                    "confidence": issue.confidence,
                    "affected_rows": issue.affected_rows,
                    "evidence": issue.evidence,
                }
                for issue, dataset_id, filename, name in rows
            ]
        }


@router.get("/issues/{run_id}")
def get_issues(run_id: str) -> dict:
    with SessionLocal() as session:
        rows = session.query(IssueRow).filter(IssueRow.run_id == run_id).all()
        return {
            "issues": [
                {
                    "id": r.agent_issue_id or r.id,
                    "type": r.issue_type,
                    "column": r.column_name,
                    "severity": r.severity,
                    "confidence": r.confidence,
                    "affected_rows": r.affected_rows,
                    "evidence": r.evidence,
                }
                for r in rows
            ]
        }


@router.get("/plan/{run_id}")
def get_plan(run_id: str) -> dict:
    with SessionLocal() as session:
        row = session.query(PlanRow).filter(PlanRow.run_id == run_id).first()
        if row is None:
            return {"actions": [], "risk_level": "LOW"}
        return {"actions": row.plan.get("actions", []), "risk_level": row.risk_level}


@router.get("/validation/{run_id}")
def get_validation(run_id: str) -> dict:
    with SessionLocal() as session:
        row = session.query(ValidationRow).filter(ValidationRow.run_id == run_id).first()
        if row is None:
            return {"status": "", "before_score": 0.0, "after_score": 0.0, "details": []}
        return {
            "status": row.result,
            "before_score": row.before_score,
            "after_score": row.after_score,
            "details": row.details,
        }
