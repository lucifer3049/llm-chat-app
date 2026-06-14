"""Chat domain: message roles. Pure business, no framework imports."""
from __future__ import annotations

import enum


class MessageRole(str, enum.Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
