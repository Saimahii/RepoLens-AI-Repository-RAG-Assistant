"""messages table: user questions and assistant answers in a chat session."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base
from app.models.types import LongText


class Message(Base):
    """One chat message. Assistant messages also store the agent and sources."""

    __tablename__ = "messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("chat_sessions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # "user" or "assistant"
    content: Mapped[str] = mapped_column(LongText, nullable=False)
    agent: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Sources list stored as a JSON string (simple and portable)
    sources_json: Mapped[str | None] = mapped_column(LongText, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Message id={self.id} role={self.role!r}>"
