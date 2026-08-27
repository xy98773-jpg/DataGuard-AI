"""Dataset & profiling schemas."""

from typing import Any

from pydantic import BaseModel, Field


class ColumnProfile(BaseModel):
    """Deterministic per-column measurements (Python profiler output)."""

    name: str
    dtype: str = "unknown"
    null_rate: float = 0.0
    unique_rate: float = 0.0
    sample_values: list[Any] = Field(default_factory=list)
    min: float | None = None
    max: float | None = None
    mean: float | None = None
    patterns: dict[str, int] = Field(default_factory=dict)


class DatasetProfile(BaseModel):
    """Full deterministic profile produced by the Python Data Profiler."""

    rows: int = 0
    columns: int = 0
    schema: dict[str, ColumnProfile] = Field(default_factory=dict)
    statistics: dict[str, Any] = Field(default_factory=dict)
    patterns: dict[str, dict[str, int]] = Field(default_factory=dict)
    anomalies: dict[str, list[dict[str, Any]]] = Field(default_factory=dict)


class DatasetInfo(BaseModel):
    id: str
    filename: str
    name: str = ""  # 数据集显示名
    source_type: str = "file"
    row_count: int = 0
    column_count: int = 0
    profile_status: str = "pending"
