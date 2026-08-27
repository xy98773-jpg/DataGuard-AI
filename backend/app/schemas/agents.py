"""Structured outputs of the core agents (validated with Pydantic).

Agents NEVER return raw JSON: the LLM output is validated against these
schemas before anything downstream consumes it.
"""

from pydantic import BaseModel, Field


class SupervisorOutput(BaseModel):
    next_node: str = "profiler"
    route: str = "file_cleaning"  # file_cleaning | database_governance
    reasoning: str = ""


class SemanticProfile(BaseModel):
    """Profiler Agent output: semantic interpretation of deterministic stats.

    The Python Data Profiler produces measurements; this Agent only explains
    them. Statistics themselves are never computed by the LLM.
    """

    summary: str = ""
    column_semantics: dict[str, str] = Field(default_factory=dict)
    notable_patterns: list[str] = Field(default_factory=list)
