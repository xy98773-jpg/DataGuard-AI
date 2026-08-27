"""Approval API: human-in-the-loop."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.workflow_service import WorkflowService

router = APIRouter(tags=["approval"])
_svc = WorkflowService()


class DecisionRequest(BaseModel):
    run_id: str
    operator: str = ""


class SubmitDecisionsRequest(BaseModel):
    run_id: str
    operator: str = ""
    decisions: dict[str, str]  # {"tool__column": "approve"|"reject"}


@router.get("/approval/pending")
def get_pending() -> dict:
    return {"approvals": _svc.get_pending_approvals()}


@router.post("/approval/approve")
def approve(req: DecisionRequest) -> dict:
    try:
        return _svc.approve(req.run_id, req.operator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approval/reject")
def reject(req: DecisionRequest) -> dict:
    try:
        return _svc.reject(req.run_id, req.operator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/approval/submit")
def submit(req: SubmitDecisionsRequest) -> dict:
    """逐条提交审批结果（部分批准/部分拒绝）."""
    try:
        return _svc.submit_decisions(req.run_id, req.decisions, req.operator)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
