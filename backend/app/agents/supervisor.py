"""Supervisor Agent — task understanding, flow planning, node routing.

Cannot modify data or execute tools.
"""

from app.agents.base import BaseAgent
from app.llm.client import LLMUsage
from app.schemas.agents import SupervisorOutput


class SupervisorAgent(BaseAgent):
    name = "supervisor"
    system_prompt_path = "supervisor.md"

    @property
    def output_schema(self) -> type[SupervisorOutput]:
        return SupervisorOutput

    def run(self, user_request: str, source_type: str) -> tuple[SupervisorOutput, LLMUsage]:
        output, usage = self.invoke(
            user=f"User goal: {user_request}\nSource type: {source_type}",
            context={"user_request": user_request, "source_type": source_type},
        )
        return output, usage
