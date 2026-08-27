"""Validation schemas: deterministic quality scoring."""

from pydantic import BaseModel, Field


class QualityScore(BaseModel):
    overall: float = 0.0  # 0-100
    dimensions: dict[str, float] = Field(default_factory=dict)


class ValidationResult(BaseModel):
    status: str = "PASS"  # PASS | FAIL
    quality_before: QualityScore | None = None
    quality_after: QualityScore | None = None
    details: list[str] = Field(default_factory=list)
