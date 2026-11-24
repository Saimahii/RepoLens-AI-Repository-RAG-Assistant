"""code_chunks table: one row per semantic chunk (function, class, method, module)."""

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database.db import Base
from app.models.types import LongText


class CodeChunk(Base):
    """A piece of code that gets embedded and searched."""

    __tablename__ = "code_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    repository_id: Mapped[int] = mapped_column(
        ForeignKey("repositories.id", ondelete="CASCADE"), nullable=False, index=True
    )
    file_id: Mapped[int] = mapped_column(
        ForeignKey("indexed_files.id", ondelete="CASCADE"), nullable=False, index=True
    )
    # Stable ID shared with ChromaDB so MySQL rows and vectors can be matched
    chunk_uid: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    file_path: Mapped[str] = mapped_column(String(1000), nullable=False)
    language: Mapped[str] = mapped_column(String(20), nullable=False)
    symbol_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    # One of: function, class, method, module
    symbol_type: Mapped[str] = mapped_column(String(20), nullable=False, default="module")
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    imports: Mapped[str | None] = mapped_column(Text, nullable=True)
    parent: Mapped[str | None] = mapped_column(String(255), nullable=True)  # e.g. class of a method
    content: Mapped[str] = mapped_column(LongText, nullable=False)

    def __repr__(self) -> str:
        return f"<CodeChunk {self.file_path}:{self.start_line}-{self.end_line} {self.symbol_name!r}>"
