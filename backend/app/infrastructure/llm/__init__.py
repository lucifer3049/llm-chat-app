"""LLM provider selection.

`get_llm_provider` returns the configured `LLMProvider` implementation. Only the
mock is available in Day 4; the Groq adapter is wired in Day 5 (PLAN §3.5).
"""
from __future__ import annotations

from app.domain.ports import LLMProvider
from app.infrastructure.config import Settings
from app.infrastructure.llm.mock import MockLLMProvider


def get_llm_provider(settings: Settings) -> LLMProvider:
    provider = settings.llm_provider.lower()
    if provider == "mock":
        return MockLLMProvider()
    if provider == "groq":
        # Real adapter (OpenAI-compatible, streaming) lands in Day 5.
        raise NotImplementedError("Groq provider is wired in Day 5; set LLM_PROVIDER=mock")
    raise ValueError(f"Unknown LLM_PROVIDER={settings.llm_provider!r} (expected 'mock' or 'groq')")
