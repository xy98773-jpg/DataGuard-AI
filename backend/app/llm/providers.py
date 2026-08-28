"""OpenAI-compatible cloud provider (OpenAI / DeepSeek / Qwen / ...).

Uses langchain-openai's ChatOpenAI pointed at the configured base_url.

Structured output strategy: plain chat completion + robust JSON parsing +
Pydantic validation. `with_structured_output` is NOT used because some
providers (e.g. deepseek-v4-flash) reject its `response_format` payload.
"""

import json
import re
import threading
import time
from collections import OrderedDict

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from app.config import settings
from app.llm.client import LLMClient, LLMUsage, _serialize_context
from app.services.llm_settings import get_llm_config

_JSON_BLOCK = re.compile(r"\{.*\}", re.DOTALL)

# ---- LLM 结果缓存（同数据重复治理节省 token）----
# LRU：key = sha256(system + user)，TTL 1 小时；仅缓存结构化输出与 usage
_CACHE_MAX = 128
_cache: "OrderedDict[str, tuple[float, str, dict]]" = OrderedDict()
_cache_lock = threading.Lock()
_cache_hits = 0
_cache_misses = 0


def _cache_key(system: str, user: str) -> str:
    import hashlib

    return hashlib.sha256(f"{system}\n---\n{user}".encode("utf-8")).hexdigest()


def _cache_get(key: str):
    global _cache_hits, _cache_misses
    with _cache_lock:
        item = _cache.get(key)
        if item is None:
            _cache_misses += 1
            return None
        ts, payload, usage = item
        if time.time() - ts > 3600:
            _cache.pop(key, None)
            _cache_misses += 1
            return None
        _cache.move_to_end(key)
        _cache_hits += 1
        return payload, usage


def cache_stats() -> dict:
    """返回 LLM 结果缓存统计（进程内计数）。"""
    with _cache_lock:
        total = _cache_hits + _cache_misses
        return {
            "hits": _cache_hits,
            "misses": _cache_misses,
            "hit_rate": round(_cache_hits / total * 100, 1) if total else 0.0,
            "size": len(_cache),
            "max_size": _CACHE_MAX,
        }


def _cache_put(key: str, payload: str, usage: dict) -> None:
    with _cache_lock:
        _cache[key] = (time.time(), payload, usage)
        _cache.move_to_end(key)
        while len(_cache) > _CACHE_MAX:
            _cache.popitem(last=False)


class OpenAICompatibleClient(LLMClient):
    def __init__(self) -> None:
        # 每次构造读取最新运行时配置（DB llm_settings 优先，回退 .env）→ 页面改配置即热生效
        cfg = get_llm_config()
        self._cfg = cfg
        self._llm = ChatOpenAI(
            model=cfg.get("model") or settings.llm_model,
            base_url=(cfg.get("base_url") or settings.llm_base_url) or None,
            api_key=(cfg.get("api_key") or settings.llm_api_key) or "not-needed",
            temperature=cfg.get("temperature", settings.llm_temperature),
            max_tokens=cfg.get("max_tokens", settings.llm_max_tokens),
            max_retries=0,  # retries handled here with JSON parsing
        )
        # 备用模型（主模型失败自动切换；鲁棒性设计）
        self._fallback_llm: ChatOpenAI | None = None
        fb_model = cfg.get("fallback_model")
        if fb_model:
            self._fallback_llm = ChatOpenAI(
                model=fb_model,
                base_url=(cfg.get("fallback_base_url") or settings.llm_fallback_base_url) or None,
                api_key=(cfg.get("fallback_api_key") or cfg.get("api_key") or settings.llm_fallback_api_key or "not-needed"),
                temperature=cfg.get("temperature", settings.llm_temperature),
                max_tokens=cfg.get("max_tokens", settings.llm_max_tokens),
                max_retries=0,
            )

    def generate_structured(self, *, system, user, schema, context=None):
        if context is not None:
            user = f"{user}\n\nStructured context:\n{_serialize_context(context)}"
        messages = [("system", system), ("user", user)]

        # 结果缓存：相同 prompt 命中则直接返回（省 token）
        ckey = _cache_key(system, user)
        hit = _cache_get(ckey)
        if hit is not None:
            payload, usage = hit
            try:
                return schema.model_validate(json.loads(payload)), LLMUsage(**usage)
            except Exception:  # noqa: BLE001 - 缓存损坏则重试
                pass

        attempts = max(1, settings.llm_max_retries + 1)
        last_error: Exception | None = None
        for _ in range(attempts):
            try:
                msg = self._invoke_with_timeout(messages)
                data = self._parse_json(msg.content)
                result = schema.model_validate(data)
                usage = self._extract_usage(msg)
                _cache_put(ckey, json.dumps(data, ensure_ascii=False, default=str), usage.model_dump())
                return result, usage
            except Exception as exc:  # noqa: BLE001 - retry on timeout/parse/validation
                last_error = exc
                # 主模型失败 → 自动切换备用模型重试一次（fallback）
                if self._fallback_llm is not None:
                    try:
                        msg = self._fallback_llm.invoke(messages)
                        data = self._parse_json(msg.content)
                        result = schema.model_validate(data)
                        usage = self._extract_usage(msg)
                        _cache_put(ckey, json.dumps(data, ensure_ascii=False, default=str), usage.model_dump())
                        return result, usage
                    except Exception as fb_exc:  # noqa: BLE001
                        last_error = fb_exc
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
