"""Unit tests for the semantic chunker (context lines, large-symbol splitting, fallback, stable chunk_uid)."""

from pathlib import Path

from app.parsers.chunker import build_chunk_uid, chunk_file
from app.utils.file_utils import ScannedFile


def _make_scanned(rel_path: str, language: str, content: str) -> ScannedFile:
    return ScannedFile(
        abs_path=Path(rel_path),
        rel_path=rel_path,
        language=language,
        content=content,
        line_count=len(content.splitlines()),
    )


def test_chunker_adds_surrounding_context_lines_and_keeps_exact_symbol_lines() -> None:
    code = """# header comment line 1
# header comment line 2
X = 10

def compute(a: int) -> int:
    return a + X

# footer line 8
# footer line 9
"""
    scanned = _make_scanned("app/math.py", "python", code)
    chunks = chunk_file(repo_id=1, scanned_file=scanned, context_lines=2)

    assert len(chunks) == 1
    chunk = chunks[0]
    assert chunk.symbol_name == "compute"
    assert chunk.symbol_type == "function"
    assert (chunk.start_line, chunk.end_line) == (5, 6)
    # Context includes 2 lines before ("X = 10") and 2 lines after ("# footer line 8")
    assert "X = 10" in chunk.content
    assert "def compute(a: int) -> int:" in chunk.content
    assert "# footer line 8" in chunk.content


def test_chunker_falls_back_gracefully_on_syntax_error() -> None:
    broken_py = "def oops(:\n    x = 1\n    y = 2\n"
    scanned = _make_scanned("app/broken.py", "python", broken_py)
    chunks = chunk_file(repo_id=7, scanned_file=scanned)

    assert len(chunks) == 1
    assert chunks[0].symbol_type == "module"
    assert chunks[0].start_line == 1
    assert chunks[0].end_line == 3
    assert "def oops(:" in chunks[0].content


def test_chunker_splits_very_large_function_into_overlapping_parts() -> None:
    lines = ["def giant_func(x: int) -> int:"]
    lines.extend(f"    x += {i}" for i in range(1, 220))
    lines.append("    return x")
    content = "\n".join(lines)

    scanned = _make_scanned("app/big.py", "python", content)
    chunks = chunk_file(
        repo_id=3,
        scanned_file=scanned,
        context_lines=0,
        max_chunk_lines=100,
        split_window_lines=80,
        split_overlap_lines=15,
    )

    assert len(chunks) == 4
    assert chunks[0].symbol_name == "giant_func (part 1/4)"
    assert chunks[-1].symbol_name == "giant_func (part 4/4)"
    assert chunks[0].start_line == 1
    assert chunks[-1].end_line == len(lines)
    # Consecutive slices overlap
    for prev, nxt in zip(chunks, chunks[1:]):
        assert nxt.start_line <= prev.end_line
    # All chunk_uids are unique
    assert len({c.chunk_uid for c in chunks}) == len(chunks)


def test_chunk_uid_is_deterministic_and_unique_across_repos() -> None:
    uid_a = build_chunk_uid(1, "app/a.py", "function", "foo", 10, 20)
    uid_b = build_chunk_uid(1, "app/a.py", "function", "foo", 10, 20)
    uid_other_repo = build_chunk_uid(2, "app/a.py", "function", "foo", 10, 20)

    assert uid_a == uid_b
    assert len(uid_a) == 32
    assert uid_a != uid_other_repo


def test_chunker_handles_module_with_no_functions_or_classes() -> None:
    config_py = 'API_URL = "http://localhost:8000"\nTIMEOUT = 30\n'
    scanned = _make_scanned("app/constants.py", "python", config_py)
    chunks = chunk_file(repo_id=1, scanned_file=scanned)

    assert len(chunks) == 1
    assert chunks[0].symbol_type == "module"
    assert "API_URL" in chunks[0].content


def test_chunker_avoids_double_part_suffix_on_long_markdown_lines() -> None:
    # 100 long markdown lines force fallback_parser windows AND char-based sub-splitting
    long_md = "\n".join(f"Line {i}: " + ("documentation " * 12) for i in range(1, 101))
    scanned = _make_scanned("README.md", "markdown", long_md)
    chunks = chunk_file(repo_id=2, scanned_file=scanned, max_chunk_chars=2500)

    assert len(chunks) > 2
    for chunk in chunks:
        assert "(part " not in (chunk.symbol_name or "") or chunk.symbol_name.count("(part") == 1
        assert ") (part" not in (chunk.symbol_name or "")
    assert len({c.chunk_uid for c in chunks}) == len(chunks)
