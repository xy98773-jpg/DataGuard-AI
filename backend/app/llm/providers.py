"""OpenAI-compatible cloud provider (OpenAI / DeepSeek / Qwen / ...).

Uses langchain-openai's ChatOpenAI pointed at the configured base_url.

Structured output strategy: plain chat completion + robust JSON parsing +
Pydantic validation. `with_structured_output` is NOT used because some
providers (e.g. deepseek-v4-flash) reject its `response_format` payload.
"""

import json
import re
import threading

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.llm.client import LLMClient, LLMUsage, _serialize_context

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)


class OpenAICompatibleClient(LLMClient):
    def __init__(self) -> None:
        self._llm = ChatOpenAI(
            model=settings.llm_model,
            base_url=settings.llm_base_url or None,
            api_key=settings.llm_api_key or "not-needed",
            temperature=settings.llm_temperature,
            max_tokens=settings.llm_max_tokens,
            max_retries=0,  # retries handled here with JSON parsing
        )

    def generate_structured(self, *, system, user, schema, context=None):
        if context is not None:
            user = f"{user}\n\nStructured context:\n{_serialize_context(context)}"
        messages = [("system", system), ("user", user)]

        attempts = max(1, settings.llm_max_retries + 1)
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                msg = self._invoke_with_timeout(messages)
                data = self._parse_json(msg.content)
                result = schema.model_validate(data)
                return result, self._extract_usage(msg)
            except Exception as exc:  # noqa: BLE001 - retry on timeout/parse/validation
                last_error = exc
        raise RuntimeError(f"LLM structured output failed after {attempts} attempts: {last_error}")

    def _invoke_with_timeout(self, messages) -> AIMessage:
        """LangChain-openai 1.x has no timeout kwarg; enforce a hard timeout.

        Uses a daemon thread + join(timeout) so a stuck HTTP call cannot block
        the workflow forever (ThreadPoolExecutor-with would wait on exit).
        """
        holder: dict = {}

        def _run() -> None:
            holder["msg"] = self._llm.invoke(messages)

        worker = threading.Thread(target=_run, daemon=True)
        worker.start()
        worker.join(timeout=settings.llm_timeout_seconds)
        if worker.is_alive():
            raise TimeoutError(f"LLM call timed out after {settings.llm_timeout_seconds}s")
        return holder["msg"]

    @staticmethod
    def _parse_json(content: str) -> dict:
        try:
            return json.loads(content)
        except Exception:
            pass
        # tolerate markdown fences / trailing text
        match = _JSON_BLOCK.search(content)
        if not match:
            raise ValueError(f"no JSON object found in model output: {content[:200]!r}")
        return json.loads(match.group(0))

    @staticmethod
    def _extract_usage(msg: AIMessage) -> LLMUsage:
        try:
            um = getattr(msg, "usage_metadata", None) or {}
            prompt = int(um.get("input_tokens", 0))
            completion = int(um.get("output_tokens", 0))
            if prompt or completion:
                return LLMUsage(prompt_tokens=prompt, completion_tokens=completion)
        except Exception:
            pass
        try:
            meta = getattr(msg, "response_metadata", None) or {}
            token_usage = meta.get("token_usage") or {}
            prompt = int(token_usage.get("prompt_tokens", 0))
            completion = int(token_usage.get("completion_tokens", 0))
            return LLMUsage(prompt_tokens=prompt, completion_tokens=completion)
        except Exception:
            return LLMUsage()
