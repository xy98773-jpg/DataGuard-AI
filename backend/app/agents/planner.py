"""Cleaning Planner Agent — generate safe cleaning plan from issues.

Never executes actions; only uses registered tools.
"""

from app.agents.base import BaseAgent
from app.llm.client import LLMUsage
from app.schemas.issue import Issue
from app.schemas.plan import CleaningPlan
from app.tools.registry import get_registry


class PlannerAgent(BaseAgent):
    name = "planner"
    system_prompt_path = "planner.md"

    @property
    def output_schema(self) -> type[CleaningPlan]:
        return CleaningPlan

    def run(self, issues: list[Issue], context: dict | None = None) -> tuple[CleaningPlan, LLMUsage]:
        base_context: dict = {
            "issues": [i.model_dump() for i in issues],
            "available_tools": get_registry().list_tools(),
        }
        if context:
            base_context.update(context)
        output, usage = self.invoke(
            user="Generate a cleaning plan for the reported issues.",
            context=base_context,
        )
        return output, usage
