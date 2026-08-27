"""Issue schemas: Quality Inspector output."""

from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import Severity


class Issue(BaseModel):
    id: str
    issue_type: str
    column: str
    severity: Severity
    confidence: float = 0.0
    affected_rows: int = 0
    evidence: list[Any] = Field(default_factory=list)


class IssueReport(BaseModel):
    issues: list[Issue] = Field(default_factory=list)
