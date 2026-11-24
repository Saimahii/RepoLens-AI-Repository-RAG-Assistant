"""Shared data structures for parsers and the semantic chunker."""

from dataclasses import dataclass, field


class ParseError(Exception):
    """Raised when a language-specific parser cannot parse a file cleanly."""


@dataclass
class ParsedSymbol:
    """One semantic code unit (function, class, method, or module window)."""

    symbol_name: str
    symbol_type: str  # "function", "class", "method", or "module"
    start_line: int  # 1-indexed, inclusive
    end_line: int  # 1-indexed, inclusive
    parent: str | None = None
    docstring: str | None = None
    decorators: list[str] = field(default_factory=list)
    routes: list[str] = field(default_factory=list)
    is_react_component: bool = False


@dataclass
class ParsedFile:
    """Structured parse result for a single source file."""

    file_path: str
    language: str
    imports: list[str] = field(default_factory=list)
    symbols: list[ParsedSymbol] = field(default_factory=list)
    used_fallback: bool = False


@dataclass
class ChunkData:
    """A ready-to-store semantic chunk matching the code_chunks table."""

    chunk_uid: str
    file_path: str
    language: str
    symbol_name: str | None
    symbol_type: str
    start_line: int
    end_line: int
    imports: str | None
    parent: str | None
    content: str
