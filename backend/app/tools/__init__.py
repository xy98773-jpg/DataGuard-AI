"""Tool layer: BaseTool interface, ToolRegistry, concrete tools.

All tool calls go through the registry — agents never import tools directly.
"""

from app.tools.cleaning import register_cleaning_tools
from app.tools.data import register_data_tools
from app.tools.registry import get_registry


def init_tools() -> None:
    """Discover & register all tools (idempotent; safe on repeated startup)."""
    get_registry().reset()
    register_cleaning_tools()
    register_data_tools()


__all__ = ["init_tools", "get_registry"]
