"""repositories table: one row per connected GitHub repository."""

from datetime import datetime

from sqlalchemy import DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base


class Repository(Base):
    """A GitHub repository that was cloned (and later indexed)."""

    __tablename__ = "repositories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    # Unique so the same repo is not cloned twice
    github_url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True, index=True)
    local_path: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    # One of: pending, cloning, parsing, embedding, done, failed
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<Repository id={self.id} name={self.name!r} status={self.status!r}>"
