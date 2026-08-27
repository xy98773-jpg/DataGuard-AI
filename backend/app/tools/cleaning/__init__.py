"""Cleaning tools registration.

Phase 1: LOW-risk set; Phase 4 adds MEDIUM (fill_missing) and HIGH
(delete_duplicate). delete_row is intentionally NOT implemented.
"""

from app.tools.cleaning.high_risk import DeleteDuplicateTool, FillMissingTool
from app.tools.cleaning.normalizers import (
    NormalizeDateTool,
    NormalizeEmailTool,
    NormalizePhoneTool,
    TrimWhitespaceTool,
)
from app.tools.registry import get_registry

_CLEANING_TOOLS = [
    NormalizePhoneTool(),
    NormalizeEmailTool(),
    NormalizeDateTool(),
    TrimWhitespaceTool(),
    FillMissingTool(),
    DeleteDuplicateTool(),
]


def register_cleaning_tools() -> None:
    reg = get_registry()
    for tool in _CLEANING_TOOLS:
        reg.register(tool)
