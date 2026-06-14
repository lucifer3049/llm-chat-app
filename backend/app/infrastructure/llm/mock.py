"""Mock LLM provider — deterministic, offline, free.

Used to wire the chat flow end-to-end before the real Groq adapter lands
(PLAN Day 4 → Day 5). It implements `app.domain.ports.LLMProvider` so swapping
in Groq later is a config change, not a code change. The reply echoes the latest
user turn with a visible marker so a demo makes the mock obvious.
"""
from __future__ import annotations

from collections.abc import Sequence

from app.domain.chat import LLMMessage, MessageRole


class MockLLMProvider:
    """Implements `app.domain.ports.LLMProvider` without any network call."""

    def complete(self, messages: Sequence[LLMMessage]) -> str:
        last_user = next(
            (m.content for m in reversed(messages) if m.role is MessageRole.USER),
            "",
        )
        return f"[mock-llm] You said: {last_user}"
