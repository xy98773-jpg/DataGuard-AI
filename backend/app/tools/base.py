"""BaseTool interface.

Every tool implements a JSON-friendly `execute(**params)` contract and a
`risk_level`. Cleaning tools additionally expose `apply(df, column, **params)`
so the Execution Engine can transform DataFrames deterministically.
"""

from abc import ABC, abstractmethod
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.common import RiskLevel


class CleaningOutput(BaseModel):
    affected_rows: int = 0
    samples: list[dict[str, Any]] = Field(default_factory=list)


class BaseTool(ABC):
    name: str = ""
    description: str = ""
    risk_level: RiskLevel = RiskLevel.LOW
    # optional Pydantic schema for parameter validation
    params_schema: type[BaseModel] | None = None

    @abstractmethod
    def execute(self, **params: Any) -> dict[str, Any]:
        """Deterministic execution; returns a JSON-serializable output dict."""

    def validate_params(self, params: dict[str, Any]) -> list[str]:
        if self.params_schema is None:
            return []
        try:
            self.params_schema.model_validate(params)
            return []
        except Exception as exc:  # noqa: BLE001 - surface validation errors
            return [str(exc)]
