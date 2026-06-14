"""Chat endpoints: session CRUD, history load, and sending a message.

Every route is gated by a coarse RBAC permission (all roles may chat); the
service enforces per-user ownership and returns 404 for foreign sessions. The
message endpoint is non-streaming here (mock LLM) — the SSE streaming variant
lands in Day 5 (PLAN §3.5).
"""
from __future__ import annotations

import uuid

from apiflask import APIBlueprint

from app.domain.user import Permission
from app.interface.deps import auth, chat_service, current_user, get_db
from app.interface.permissions import require_permission
from app.interface.schemas import (
    ChatSessionDetailOut,
    ChatSessionOut,
    CreateSessionIn,
    MessageOut,
    SendMessageIn,
    SendMessageOut,
)

chat_bp = APIBlueprint("chat", __name__, url_prefix="/chat", tag="Chat")


@chat_bp.post("/sessions")
@chat_bp.auth_required(auth)
@chat_bp.input(CreateSessionIn)
@chat_bp.output(ChatSessionOut, status_code=201)
@chat_bp.doc(summary="Create a chat session")
@require_permission(Permission.USE_CHAT)
def create_session(json_data: dict):
    session = chat_service().create_session(current_user(), json_data.get("title"))
    get_db().commit()
    return session


@chat_bp.get("/sessions")
@chat_bp.auth_required(auth)
@chat_bp.output(ChatSessionOut(many=True))
@chat_bp.doc(summary="List own sessions", description="Most-recently-active first.")
@require_permission(Permission.MANAGE_OWN_CHATS)
def list_sessions():
    return chat_service().list_sessions(current_user())


@chat_bp.get("/sessions/<uuid:session_id>")
@chat_bp.auth_required(auth)
@chat_bp.output(ChatSessionDetailOut)
@chat_bp.doc(
    summary="Load a session with history",
    description="Returns the session and its messages in chronological order. "
    "404 if the session does not exist or belongs to another user.",
)
@require_permission(Permission.MANAGE_OWN_CHATS)
def get_session(session_id: uuid.UUID):
    return chat_service().get_session(current_user(), session_id)


@chat_bp.delete("/sessions/<uuid:session_id>")
@chat_bp.auth_required(auth)
@chat_bp.output(MessageOut)
@chat_bp.doc(summary="Delete own session", description="Cascades to its messages.")
@require_permission(Permission.MANAGE_OWN_CHATS)
def delete_session(session_id: uuid.UUID):
    chat_service().delete_session(current_user(), session_id)
    get_db().commit()
    return {"message": "Session deleted."}


@chat_bp.post("/sessions/<uuid:session_id>/messages")
@chat_bp.auth_required(auth)
@chat_bp.input(SendMessageIn)
@chat_bp.output(SendMessageOut, status_code=201)
@chat_bp.doc(
    summary="Send a message",
    description="Persists the user message, gets the assistant reply (mock LLM in "
    "this phase), persists it, and returns both. Streaming arrives in Day 5.",
)
@require_permission(Permission.USE_CHAT)
def send_message(session_id: uuid.UUID, json_data: dict):
    result = chat_service().send_message(current_user(), session_id, json_data["content"])
    get_db().commit()
    return result
