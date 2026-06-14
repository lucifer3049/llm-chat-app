"""Chat use cases: session CRUD, history load, and sending a message.

Ownership is the real authorisation boundary here (the RBAC matrix only gates
"may use chat at all"): every session lookup is scoped to the acting user, and a
session owned by someone else is reported as 404 — never 403 — so the API does
not leak which session ids exist (PLAN §3.3).

Message ordering: history sorts by `created_at`, but relying on the wall clock
is unsafe — Postgres `now()` is transaction-start time (so a user/assistant pair
written in one request would tie), and a coarse OS clock can hand two requests
the same reading. So instead of trusting `now()`, each new message is stamped
strictly after the last message already in the session. That keeps chronological
history deterministic without adding a separate sequence column.
"""
from __future__ import annotations

import datetime as dt
import uuid

from app.application.errors import NotFoundError, ValidationError
from app.domain.chat import LLMMessage, MessageRole
from app.domain.ports import ChatRepository, LLMProvider
from app.infrastructure.db.models import ChatSession, Message, User

MAX_TITLE_LENGTH = 60
MAX_MESSAGE_LENGTH = 8000


class ChatService:
    def __init__(self, chats: ChatRepository, llm: LLMProvider) -> None:
        self._chats = chats
        self._llm = llm

    def create_session(self, actor: User, title: str | None = None) -> ChatSession:
        session = ChatSession(
            user_id=actor.id,
            title=(title.strip() or None) if title else None,
        )
        return self._chats.add_session(session)

    def list_sessions(self, actor: User) -> list[ChatSession]:
        return self._chats.list_sessions(actor.id)

    def get_session(self, actor: User, session_id: uuid.UUID) -> dict:
        """A session plus its messages in chronological order (history load)."""
        session = self._owned_session(actor, session_id)
        messages = self._chats.list_messages(session.id)
        return {
            "id": session.id,
            "title": session.title,
            "created_at": session.created_at,
            "updated_at": session.updated_at,
            "messages": messages,
        }

    def delete_session(self, actor: User, session_id: uuid.UUID) -> None:
        session = self._owned_session(actor, session_id)
        self._chats.delete_session(session)

    def send_message(self, actor: User, session_id: uuid.UUID, content: str) -> dict:
        """Persist the user turn, get the LLM reply, persist it, return both."""
        content = content.strip()
        if not content:
            raise ValidationError("Message content is required")
        if len(content) > MAX_MESSAGE_LENGTH:
            raise ValidationError(
                f"Message must be at most {MAX_MESSAGE_LENGTH} characters"
            )

        session = self._owned_session(actor, session_id)
        history = self._chats.list_messages(session.id)

        # Stamp strictly after the last existing turn (see module docstring).
        base = dt.datetime.now(dt.timezone.utc)
        if history:
            base = max(base, history[-1].created_at + dt.timedelta(microseconds=1))
        user_msg = self._chats.add_message(
            Message(
                session_id=session.id,
                role=MessageRole.USER,
                content=content,
                created_at=base,
            )
        )

        prompt = [LLMMessage(role=m.role, content=m.content) for m in history]
        prompt.append(LLMMessage(role=MessageRole.USER, content=content))
        reply = self._llm.complete(prompt)

        assistant_msg = self._chats.add_message(
            Message(
                session_id=session.id,
                role=MessageRole.ASSISTANT,
                content=reply,
                created_at=base + dt.timedelta(microseconds=1),
            )
        )

        # First turn names the session; bump updated_at so the list resorts.
        if session.title is None:
            session.title = self._derive_title(content)
        session.updated_at = assistant_msg.created_at

        return {"user_message": user_msg, "assistant_message": assistant_msg}

    # ---- helpers ----
    def _owned_session(self, actor: User, session_id: uuid.UUID) -> ChatSession:
        session = self._chats.get_session(session_id)
        # 404 (not 403) for a missing OR foreign session: don't leak existence.
        if session is None or session.user_id != actor.id:
            raise NotFoundError("Session not found")
        return session

    @staticmethod
    def _derive_title(content: str) -> str:
        single_line = " ".join(content.split())
        if len(single_line) <= MAX_TITLE_LENGTH:
            return single_line
        return single_line[: MAX_TITLE_LENGTH - 1].rstrip() + "…"
