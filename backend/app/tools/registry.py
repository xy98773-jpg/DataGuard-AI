"""Tool Registry.

Agents NEVER import concrete tools; they resolve tools through the registry:
    tool = registry.get("normalize_phone")
    result = tool.execute(...)
"""

from loguru import logger

from app.tools.base import BaseTool


class ToolRegistry:
    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    def register(self, tool: BaseTool) -> None:
        if not tool.name:
            raise ValueError("tool name is required")
        if tool.name in self._tools:
            raise ValueError(f"duplicate tool name: {tool.name}")
        self._tools[tool.name] = tool
        logger.debug(f"tool registered: {tool.name} (risk={tool.risk_level.value})")

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def has(self, name: str) -> bool:
        return name in self._tools

    def list_tools(self) -> list[dict]:
        return [
            {
                "name": t.name,
                "description": t.description,
                "risk_level": t.risk_level.value,
            }
            for t in self._tools.values()
        ]

    def reset(self) -> None:
        """Clear all tools (idempotent re-registration for tests/startup)."""
        self._tools.clear()


_registry = ToolRegistry()


def get_registry() -> ToolRegistry:
    return _registry
