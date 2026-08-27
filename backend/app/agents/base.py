"""Base agent: shared LLM invocation + prompt loading.

Agents only do understanding / judgment / planning. All computation,
statistics, validation and execution live in deterministic Python.
"""

from abc import ABC
from typing import TypeVar

from pydantic import BaseModel

from app.config import BASE_DIR
from app.llm.client import LLMClient, LLMUsage, get_llm_client
from app.trace import TraceCollector, get_collector

T = TypeVar("T", bound=BaseModel)


class BaseAgent(ABC):
    name: str = ""
    system_prompt_path: str = ""

    def __init__(
        self,
        llm: LLMClient | None = None,
        collector: TraceCollector | None = None,
    ) -> None:
        self._llm = llm or get_llm_client()
        self._collector = collector or get_collector()

    @property
    def output_schema(self) -> type[BaseModel]:
        raise NotImplementedError

    def system_prompt(self) -> str:
        path = BASE_DIR / "prompts" / self.system_prompt_path
        return path.read_text(encoding="utf-8")

    def invoke(
        self,
        *,
        user: str,
        context: dict | None = None,
    ) -> tuple[T, LLMUsage]:
        """Call LLM via the client layer; output validated against schema."""
        return self._llm.generate_structured(
            system=self.system_prompt(),
            user=user,
            schema=self.output_schema,
            context=context,
        )
