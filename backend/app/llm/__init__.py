"""LLM client layer: Agent -> LLMClient interface -> Provider -> Cloud API.

Agents must NOT call provider SDKs directly. FakeLLM exists only for
unit tests / CI / offline dev, never as a production run mode.
"""
