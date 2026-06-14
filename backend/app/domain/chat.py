"""Chat domain: message roles and the LLM message value object.

Pure business, no framework imports.
"""
from __future__ import annotations

import enum
from dataclasses import dataclass


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass(frozen=True)
class LLMMessage:
    """A single turn handed to the LLM provider.

    Decouples the provider contract from the ORM `Message`: the application maps
    persisted messages into these before calling `LLMProvider.complete`.
    """

    role: MessageRole
    content: str
