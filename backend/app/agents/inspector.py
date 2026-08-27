"""Quality Inspector Agent — detect data quality issues from evidence."""

from app.agents.base import BaseAgent
from app.llm.client import LLMUsage
from app.schemas.evidence import Evidence
from app.schemas.issue import IssueReport


class InspectorAgent(BaseAgent):
    name = "inspector"
    system_prompt_path = "inspector.md"

    @property
    def output_schema(self) -> type[IssueReport]:
        return IssueReport

    def run(self, evidence: Evidence) -> tuple[IssueReport, LLMUsage]:
        output, usage = self.invoke(
            user="Inspect the evidence and report data quality issues.",
            context={"evidence": evidence.model_dump()},
        )
        return output, usage
