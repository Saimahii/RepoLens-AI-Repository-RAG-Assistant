"""Fallback line-window parser for .java, .go, .md, and any file that fails AST/Tree-sitter parsing."""

from pathlib import Path

from app.parsers.models import ParsedFile, ParsedSymbol

DEFAULT_WINDOW_LINES: int = 80
DEFAULT_OVERLAP_LINES: int = 15


def _extract_simple_imports(language: str, lines: list[str]) -> list[str]:
    """Best-effort import extraction for Java and Go files."""
    imports: list[str] = []
    if language == "java":
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import "):
                imports.append(stripped)
    elif language == "go":
        in_block = False
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("import ("):
                in_block = True
                continue
            if in_block:
                if stripped.startswith(")"):
                    in_block = False
                elif stripped and not stripped.startswith("//"):
                    imports.append(f"import {stripped}")
            elif stripped.startswith("import "):
                imports.append(stripped)
    return imports


def parse_fallback(
    file_path: str,
    language: str,
    content: str,
    window_lines: int = DEFAULT_WINDOW_LINES,
    overlap_lines: int = DEFAULT_OVERLAP_LINES,
) -> ParsedFile:
    """Split a file into overlapping line windows so indexing never fails on any file."""
    lines = content.splitlines()
    total_lines = len(lines)
    if total_lines == 0:
        return ParsedFile(file_path=file_path, language=language, imports=[], symbols=[], used_fallback=True)

    step = max(1, window_lines - overlap_lines)
    filename = Path(file_path).name
    symbols: list[ParsedSymbol] = []

    start_idx = 0
    part = 1
    while start_idx < total_lines:
        end_idx = min(total_lines, start_idx + window_lines)
        start_line = start_idx + 1  # 1-indexed
        end_line = end_idx  # 1-indexed, inclusive

        name = filename if (part == 1 and end_idx >= total_lines) else f"{filename} (part {part})"
        symbols.append(
            ParsedSymbol(
                symbol_name=name,
                symbol_type="module",
                start_line=start_line,
                end_line=end_line,
                parent=None,
            )
        )

        if end_idx >= total_lines:
            break
        start_idx += step
        part += 1

    return ParsedFile(
        file_path=file_path,
        language=language,
        imports=_extract_simple_imports(language, lines),
        symbols=symbols,
        used_fallback=True,
    )
