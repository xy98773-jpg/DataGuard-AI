"""LLM Client Layer.

Chain: Agent -> LLMClient interface -> Provider -> Cloud LLM API.

- Agents must NOT import provider SDKs (openai/langchain) directly.
- All structured outputs are validated against a Pydantic schema.
- FakeLLM exists ONLY for unit tests / CI / offline dev; it is NOT a
  production run mode and must never fake real reasoning in the final demo.
"""

import json
from abc import ABC, abstractmethod
from typing import TypeVar

from pydantic import BaseModel

from app.config import settings

T = TypeVar("T", bound=BaseModel)


class LLMUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def total(self) -> int:
        return self.prompt_tokens + self.completion_tokens


class LLMClient(ABC):
    """Interface all agents use to talk to the LLM."""

    @abstractmethod
    def generate_structured(
        self,
        *,
        system: str,
        user: str,
        schema: type[T],
        context: dict | None = None,
    ) -> tuple[T, LLMUsage]:
        """Invoke the model and return (validated structured output, usage).

        `context` carries structured data (evidence/issues/plan) that the
        provider serializes into the prompt; FakeLLM consumes it directly.
        """


def _serialize_context(context: dict | None) -> str:
    if not context:
        return ""
    return json.dumps(context, ensure_ascii=False, default=str)


def get_llm_client() -> LLMClient:
    """Factory: returns the configured LLM client (singleton-ish)."""
    if settings.llm_provider == "fake":
        from app.llm.fake_llm import FakeLLM

        return FakeLLM()
    from app.llm.providers import OpenAICompatibleClient

    return OpenAICompatibleClient()
