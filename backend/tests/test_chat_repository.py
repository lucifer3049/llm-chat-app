"""SqlChatRepository integration tests against a real (SQLite) session.

Covers the index-aligned hot paths: session list ordering, chronological
history, per-user scoping, and FK cascade on delete.
"""
from __future__ import annotations

import datetime as dt

import pytest
from sqlalchemy import func, select

from app.domain.chat import MessageRole
from app.domain.user import Role
from app.infrastructure.db.models import ChatSession, Message, User
from app.infrastructure.db.repositories import SqlChatRepository


def _make_user(db, username="owner") -> User:
    user = User(username=username, password_hash="x", role=Role.USER, is_active=True)
    db.add(user)
    db.flush()
    return user


def _ts(seconds: int) -> dt.datetime:
    return dt.datetime(2026, 1, 1, 0, 0, seconds, tzinfo=dt.timezone.utc)


@pytest.fixture
def repo(db_session) -> SqlChatRepository:
    return SqlChatRepository(db_session)


def test_add_and_get_session(db_session, repo):
    user = _make_user(db_session)
    session = repo.add_session(ChatSession(user_id=user.id, title="hello"))
    db_session.commit()
    assert repo.get_session(session.id).title == "hello"


def test_list_sessions_most_recent_first(db_session, repo):
    user = _make_user(db_session)
    old = repo.add_session(
        ChatSession(user_id=user.id, title="old", updated_at=_ts(1))
    )
    new = repo.add_session(
        ChatSession(user_id=user.id, title="new", updated_at=_ts(2))
    )
    db_session.commit()

    sessions = repo.list_sessions(user.id)
    assert [s.id for s in sessions] == [new.id, old.id]


def test_list_sessions_scoped_per_user(db_session, repo):
    alice = _make_user(db_session, "alice")
    bob = _make_user(db_session, "bob")
    repo.add_session(ChatSession(user_id=alice.id))
    repo.add_session(ChatSession(user_id=bob.id))
    db_session.commit()
    assert len(repo.list_sessions(alice.id)) == 1


def test_list_messages_chronological(db_session, repo):
    user = _make_user(db_session)
    session = repo.add_session(ChatSession(user_id=user.id))
    repo.add_message(
        Message(session_id=session.id, role=MessageRole.ASSISTANT, content="a", created_at=_ts(2))
    )
    repo.add_message(
        Message(session_id=session.id, role=MessageRole.USER, content="u", created_at=_ts(1))
    )
    db_session.commit()

    msgs = repo.list_messages(session.id)
    assert [m.content for m in msgs] == ["u", "a"]


def test_delete_session_cascades_to_messages(db_session, repo):
    user = _make_user(db_session)
    session = repo.add_session(ChatSession(user_id=user.id))
    repo.add_message(
        Message(session_id=session.id, role=MessageRole.USER, content="hi", created_at=_ts(1))
    )
    db_session.commit()

    repo.delete_session(session)
    db_session.commit()

    remaining = db_session.scalar(select(func.count()).select_from(Message))
    assert remaining == 0
    assert repo.get_session(session.id) is None
