"""DB package: re-export Base and models so Alembic autogenerate sees metadata."""
from app.infrastructure.db.base import Base
from app.infrastructure.db.models import ChatSession, Message, User

__all__ = ["Base", "User", "ChatSession", "Message"]
