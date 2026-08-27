"""Profiler Agent — semantic interpretation of deterministic statistics.

Python computes; this Agent only explains.
"""

from app.agents.base import BaseAgent
from app.llm.client import LLMUsage
from app.schemas.agents import SemanticProfile
from app.schemas.dataset import DatasetProfile


class ProfilerAgent(BaseAgent):
    name = "profiler"
    system_prompt_path = "profiler.md"

    @property
    def output_schema(self) -> type[SemanticProfile]:
        return SemanticProfile

    def run(self, profile: DatasetProfile) -> tuple[SemanticProfile, LLMUsage]:
        output, usage = self.invoke(
            user="Interpret the dataset profile and produce a semantic dataset profile.",
            context={"profile": profile.model_dump()},
        )
        return output, usage
