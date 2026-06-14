"""ChatService tests: ownership boundary, persistence, ordering, titling.

Pure unit tests over fake repository + fake LLM (no DB, no network).
"""
from __future__ import annotations

import uuid

import pytest

from app.application.chat_service import ChatService
from app.application.errors import NotFoundError, ValidationError
from app.domain.chat import MessageRole
from app.domain.user import Role
from app.infrastructure.db.models import User


def make_user(role: Role = Role.USER) -> User:
    return User(
        id=uuid.uuid4(),
        username=f"user-{uuid.uuid4().hex[:8]}",
        password_hash="x",
        role=role,
        is_active=True,
    )


@pytest.fixture
def svc(fake_chats, fake_llm) -> ChatService:
    return ChatService(fake_chats, fake_llm)


# ---- create / list ----
def test_create_session_without_title(svc):
    user = make_user()
    session = svc.create_session(user)
    assert session.user_id == user.id
    assert session.title is None


def test_create_session_blank_title_becomes_none(svc):
    session = svc.create_session(make_user(), title="   ")
    assert session.title is None


def test_list_sessions_scoped_to_owner(svc):
    alice, bob = make_user(), make_user()
    svc.create_session(alice)
    svc.create_session(alice)
    svc.create_session(bob)
    assert len(svc.list_sessions(alice)) == 2
    assert len(svc.list_sessions(bob)) == 1


# ---- send_message ----
def test_send_message_persists_user_and_assistant(svc, fake_llm):
    fake_llm.reply = "hello back"
    user = make_user()
    session = svc.create_session(user)

    result = svc.send_message(user, session.id, "hi")

    assert result["user_message"].role is MessageRole.USER
    assert result["user_message"].content == "hi"
    assert result["assistant_message"].role is MessageRole.ASSISTANT
    assert result["assistant_message"].content == "hello back"


def test_send_message_history_is_chronological(svc):
    user = make_user()
    session = svc.create_session(user)
    svc.send_message(user, session.id, "first")
    svc.send_message(user, session.id, "second")

    detail = svc.get_session(user, session.id)
    contents = [(m.role, m.content) for m in detail["messages"]]
    assert contents == [
        (MessageRole.USER, "first"),
        (MessageRole.ASSISTANT, "fake reply"),
        (MessageRole.USER, "second"),
        (MessageRole.ASSISTANT, "fake reply"),
    ]


def test_send_message_passes_full_history_to_llm(svc, fake_llm):
    user = make_user()
    session = svc.create_session(user)
    svc.send_message(user, session.id, "first")
    svc.send_message(user, session.id, "second")
    # Prior turns (user+assistant) plus the new user turn are handed to the LLM.
    assert [m.content for m in fake_llm.last_prompt] == [
        "first",
        "fake reply",
        "second",
    ]


def test_first_message_sets_title(svc):
    user = make_user()
    session = svc.create_session(user)
    svc.send_message(user, session.id, "What is the capital of France?")
    assert session.title == "What is the capital of France?"


def test_title_not_overwritten_by_second_message(svc):
    user = make_user()
    session = svc.create_session(user, title="My chat")
    svc.send_message(user, session.id, "anything")
    assert session.title == "My chat"


def test_long_title_is_truncated(svc):
    user = make_user()
    session = svc.create_session(user)
    svc.send_message(user, session.id, "word " * 50)
    assert len(session.title) <= 60
    assert session.title.endswith("…")


def test_blank_message_rejected(svc):
    user = make_user()
    session = svc.create_session(user)
    with pytest.raises(ValidationError):
        svc.send_message(user, session.id, "   ")


# ---- ownership boundary ----
def test_get_foreign_session_is_404(svc):
    alice, bob = make_user(), make_user()
    session = svc.create_session(alice)
    with pytest.raises(NotFoundError):
        svc.get_session(bob, session.id)


def test_send_to_foreign_session_is_404(svc):
    alice, bob = make_user(), make_user()
    session = svc.create_session(alice)
    with pytest.raises(NotFoundError):
        svc.send_message(bob, session.id, "hi")


def test_delete_foreign_session_is_404(svc):
    alice, bob = make_user(), make_user()
    session = svc.create_session(alice)
    with pytest.raises(NotFoundError):
        svc.delete_session(bob, session.id)


def test_get_missing_session_is_404(svc):
    with pytest.raises(NotFoundError):
        svc.get_session(make_user(), uuid.uuid4())


def test_delete_session_removes_it(svc):
    user = make_user()
    session = svc.create_session(user)
    svc.send_message(user, session.id, "hi")
    svc.delete_session(user, session.id)
    assert svc.list_sessions(user) == []
    with pytest.raises(NotFoundError):
        svc.get_session(user, session.id)
