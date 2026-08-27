"""Tool schemas: registry-facing contracts."""

from pydantic import BaseModel, Field


class ToolCall(BaseModel):
    tool: str
    parameters: dict = Field(default_factory=dict)


class ToolResult(BaseModel):
    tool: str
    success: bool = True
    output: dict = Field(default_factory=dict)
    affected_rows: int = 0
    error: str | None = None
    latency: float = 0.0
