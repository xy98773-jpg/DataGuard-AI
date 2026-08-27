"""Cleaning plan schemas: Cleaning Planner output + Plan Validation."""

from pydantic import BaseModel, Field

from app.schemas.common import RiskLevel


class PlanAction(BaseModel):
    tool: str
    column: str
    parameters: dict = Field(default_factory=dict)
    risk: RiskLevel = RiskLevel.LOW
    issue_id: str | None = None


class CleaningPlan(BaseModel):
    actions: list[PlanAction] = Field(default_factory=list)


class PlanValidation(BaseModel):
    status: str = "PASS"  # PASS | FAIL
    reason: str = ""
    details: list[str] = Field(default_factory=list)
