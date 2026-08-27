"""Evidence schema: the compressed LLM context.

Evidence Builder controls how much data reaches the model. The full dataset
must NEVER be passed to the LLM.
"""

from typing import Any

from pydantic import BaseModel, Field


class Evidence(BaseModel):
    rows: int = 0
    columns: int = 0
    schema_summary: dict[str, dict[str, Any]] = Field(default_factory=dict)
    statistics: dict[str, dict[str, Any]] = Field(default_factory=dict)
    sample_rows: list[dict[str, Any]] = Field(default_factory=list)
    # column -> list of deterministic anomaly candidates
    candidate_anomalies: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)
