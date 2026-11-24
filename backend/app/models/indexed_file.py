"""indexed_files table: one row per source file that was scanned."""

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base


class IndexedFile(Base):
    """A source file inside a repository."""

    __tablename__ = "indexed_files"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # ON DELETE CASCADE: deleting a repository removes its files automatically
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)  # relative, forward slashes
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, server_default=func.now())

    def __repr__(self) -> str:
        return f"<IndexedFile id={self.id} path={self.file_path!r}>"
