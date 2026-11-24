"""Semantic chunker: routes files to parsers, adds context lines, splits large symbols, builds chunk_uid."""

import hashlib
import re

from app.parsers.fallback_parser import parse_fallback
from app.parsers.js_parser import parse_js
from app.parsers.models import ChunkData, ParsedFile, ParsedSymbol, ParseError
from app.parsers.python_parser import parse_python
from app.utils.file_utils import ScannedFile
from app.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CONTEXT_LINES: int = 3
DEFAULT_MAX_CHUNK_LINES: int = 150
DEFAULT_MAX_CHUNK_CHARS: int = 6000
DEFAULT_SPLIT_WINDOW_LINES: int = 120
DEFAULT_SPLIT_OVERLAP_LINES: int = 20
MAX_IMPORTS_CHARS: int = 4000


def build_chunk_uid(
    repo_id: int,
    file_path: str,
    symbol_type: str,
    symbol_name: str | None,
    start_line: int,
    end_line: int,
    occurrence: int = 0,
) -> str:
    """Create a deterministic 32-char hex ID shared between MySQL and ChromaDB."""
    raw_key = f"{repo_id}|{file_path}|{symbol_type}|{symbol_name or ''}|{start_line}|{end_line}|{occurrence}"
    return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:32]


def parse_file(scanned_file: ScannedFile) -> ParsedFile:
    """Route a scanned file to its language parser, falling back cleanly on any parse failure."""
    language = scanned_file.language
    file_path = scanned_file.rel_path
    content = scanned_file.content

    if language in {"java", "go", "markdown"}:
        return parse_fallback(file_path, language, content)

    try:
        if language == "python":
            parsed = parse_python(file_path, content)
        elif language in {"javascript", "typescript", "tsx"}:
            parsed = parse_js(file_path, content, language)
        else:
            return parse_fallback(file_path, language, content)
    except ParseError as error:
        logger.warning("Falling back to line-window chunking for %s: %s", file_path, error)
        return parse_fallback(file_path, language, content)
    except Exception as error:  # safety net: a single bad file must never crash indexing
        logger.warning("Unexpected parser error in %s (%s); using fallback chunker.", file_path, error)
        return parse_fallback(file_path, language, content)

    # If a valid source file defines no functions/classes (e.g. constants/config module),
    # fall back to line windows while keeping the extracted imports.
    if not parsed.symbols:
        fallback = parse_fallback(file_path, language, content)
        fallback.imports = parsed.imports or fallback.imports
        return fallback

    return parsed


def _split_symbol_ranges(
    lines: list[str],
    symbol: ParsedSymbol,
    max_chunk_lines: int,
    max_chunk_chars: int,
    split_window_lines: int,
    split_overlap_lines: int,
) -> list[tuple[int, int, str]]:
    """Return a list of (start_line, end_line, display_name) slices for a symbol.

    Normal symbols return a single slice. Oversized symbols are split into
    overlapping line windows so each chunk stays digestible for embeddings/LLMs.
    """
    total_lines = len(lines)
    start_line = max(1, min(symbol.start_line, total_lines))
    end_line = max(start_line, min(symbol.end_line, total_lines))
    span_lines = end_line - start_line + 1
    symbol_text = "\n".join(lines[start_line - 1 : end_line])

    if span_lines <= max_chunk_lines and len(symbol_text) <= max_chunk_chars:
        return [(start_line, end_line, symbol.symbol_name)]

    # Pick a sensible window size if lines themselves are unusually long
    window = split_window_lines
    if len(symbol_text) > max_chunk_chars and span_lines > 0:
        avg_chars_per_line = max(1, len(symbol_text) // span_lines)
        char_based_window = max(15, max_chunk_chars // avg_chars_per_line)
        window = min(window, char_based_window)

    overlap = min(split_overlap_lines, max(1, window // 4))
    step = max(1, window - overlap)

    ranges: list[tuple[int, int]] = []
    cur = start_line
    while cur <= end_line:
        part_end = min(end_line, cur + window - 1)
        ranges.append((cur, part_end))
        if part_end >= end_line:
            break
        cur += step

    total_parts = len(ranges)
    # Strip any earlier "(part N)" suffix from fallback windows so we never emit "(part 1) (part 1/2)"
    base_name = re.sub(r"\s*\(part\s+[^)]+\)$", "", symbol.symbol_name).strip()
    is_fallback_part = base_name != symbol.symbol_name
    if is_fallback_part:
        return [
            (part_start, part_end, f"{base_name} (lines {part_start}-{part_end})")
            for part_start, part_end in ranges
        ]
    return [
        (part_start, part_end, f"{base_name} (part {idx}/{total_parts})")
        for idx, (part_start, part_end) in enumerate(ranges, start=1)
    ]


def _format_imports(imports: list[str]) -> str | None:
    """Join file imports into one text field, truncated safely if unusually long."""
    if not imports:
        return None
    joined = "\n".join(imports)
    if len(joined) > MAX_IMPORTS_CHARS:
        return joined[: MAX_IMPORTS_CHARS - 3] + "..."
    return joined


def chunk_file(
    repo_id: int,
    scanned_file: ScannedFile,
    context_lines: int = DEFAULT_CONTEXT_LINES,
    max_chunk_lines: int = DEFAULT_MAX_CHUNK_LINES,
    max_chunk_chars: int = DEFAULT_MAX_CHUNK_CHARS,
    split_window_lines: int = DEFAULT_SPLIT_WINDOW_LINES,
    split_overlap_lines: int = DEFAULT_SPLIT_OVERLAP_LINES,
) -> list[ChunkData]:
    """Parse one file and turn its symbols into semantic chunks with surrounding context."""
    lines = scanned_file.content.splitlines()
    total_lines = len(lines)
    if total_lines == 0:
        return []

    parsed = parse_file(scanned_file)
    imports_text = _format_imports(parsed.imports)
    # Fallback windows already overlap, so only AST/Tree-sitter symbols need extra context lines
    extra_context = 0 if parsed.used_fallback else max(0, context_lines)

    chunks: list[ChunkData] = []
    seen_uids: set[str] = set()

    for symbol in parsed.symbols:
        slices = _split_symbol_ranges(
            lines=lines,
            symbol=symbol,
            max_chunk_lines=max_chunk_lines,
            max_chunk_chars=max_chunk_chars,
            split_window_lines=split_window_lines,
            split_overlap_lines=split_overlap_lines,
        )

        for slice_start, slice_end, chunk_name in slices:
            ctx_start = max(1, slice_start - extra_context)
            ctx_end = min(total_lines, slice_end + extra_context)
            chunk_content = "\n".join(lines[ctx_start - 1 : ctx_end])

            occurrence = 0
            uid = build_chunk_uid(
                repo_id=repo_id,
                file_path=scanned_file.rel_path,
                symbol_type=symbol.symbol_type,
                symbol_name=chunk_name,
                start_line=slice_start,
                end_line=slice_end,
                occurrence=occurrence,
            )
            while uid in seen_uids:
                occurrence += 1
                uid = build_chunk_uid(
                    repo_id=repo_id,
                    file_path=scanned_file.rel_path,
                    symbol_type=symbol.symbol_type,
                    symbol_name=chunk_name,
                    start_line=slice_start,
                    end_line=slice_end,
                    occurrence=occurrence,
                )
            seen_uids.add(uid)

            chunks.append(
                ChunkData(
                    chunk_uid=uid,
                    file_path=scanned_file.rel_path,
                    language=scanned_file.language,
                    symbol_name=chunk_name,
                    symbol_type=symbol.symbol_type,
                    start_line=slice_start,
                    end_line=slice_end,
                    imports=imports_text,
                    parent=symbol.parent,
                    content=chunk_content,
                )
            )

    return chunks
