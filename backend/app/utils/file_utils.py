"""File system helpers and repository file scanner (Windows-safe)."""

from dataclasses import dataclass
import os
import shutil
import stat
from pathlib import Path
from typing import Callable

from app.utils.logger import get_logger

logger = get_logger(__name__)

# Folders that never hold project source code and should be skipped completely
IGNORED_DIRS: frozenset[str] = frozenset(
    {
        "node_modules",
        "dist",
        "build",
        ".git",
        "venv",
        ".venv",
        "__pycache__",
    }
)

# File extensions supported by RepoLens -> canonical language names
ALLOWED_EXTENSIONS: dict[str, str] = {
    ".py": "python",
    ".js": "javascript",
    ".ts": "typescript",
    ".tsx": "tsx",
    ".java": "java",
    ".go": "go",
    ".md": "markdown",
}

# Skip very large files (minified bundles, generated dumps, etc.)
MAX_FILE_SIZE_BYTES: int = 1 * 1024 * 1024  # 1 MB


@dataclass(frozen=True)
class ScannedFile:
    """A single readable source file discovered in a cloned repository."""

    abs_path: Path
    rel_path: str  # relative to repo root, always using forward slashes
    language: str
    content: str
    line_count: int


def ensure_dir(path: Path) -> Path:
    """Create a folder (and parents) if it does not exist, then return it."""
    path.mkdir(parents=True, exist_ok=True)
    return path


def _make_writable_and_retry(func: Callable[[str], object], path: str, exc: BaseException) -> None:
    """rmtree error handler.

    Git marks files in .git/objects as read-only. On Windows, read-only files
    cannot be deleted, so we clear the flag and try again.
    """
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError as retry_error:
        logger.warning("Could not delete %s: %s (original error: %s)", path, retry_error, exc)


def safe_rmtree(path: Path) -> None:
    """Delete a folder tree, handling read-only files. Never raises."""
    if not path.exists():
        return
    try:
        shutil.rmtree(path, onexc=_make_writable_and_retry)
    except OSError as error:
        logger.warning("Failed to remove folder %s: %s", path, error)


def detect_language(path: Path) -> str | None:
    """Return the canonical language name for a file path, or None if unsupported."""
    return ALLOWED_EXTENSIONS.get(path.suffix.lower())


def read_text_file(path: Path, max_bytes: int = MAX_FILE_SIZE_BYTES) -> str | None:
    """Read a UTF-8 text file safely, skipping files > max_bytes, binaries, or bad encodings.

    Returns normalized text (LF line endings), or None if the file should be skipped.
    """
    try:
        if not path.is_file():
            return None
        file_size = path.stat().st_size
    except OSError as error:
        logger.warning("Could not stat file %s: %s", path, error)
        return None

    if file_size > max_bytes:
        logger.info("Skipping large file (%d bytes > %d): %s", file_size, max_bytes, path.name)
        return None

    try:
        raw = path.read_bytes()
    except OSError as error:
        logger.warning("Could not read file %s: %s", path, error)
        return None

    # Null bytes are a reliable indicator of binary content
    if b"\x00" in raw:
        logger.info("Skipping binary file: %s", path.name)
        return None

    try:
        # utf-8-sig handles both normal UTF-8 and UTF-8 with BOM
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        logger.warning("Skipping undecodable (non-UTF-8) file: %s", path.name)
        return None

    # Normalize CRLF/CR to LF so line numbers and snippets behave consistently on Windows
    return text.replace("\r\n", "\n").replace("\r", "\n")


def scan_repository_files(repo_root: Path) -> list[ScannedFile]:
    """Walk a cloned repository and return all supported, readable source files."""
    if not repo_root.is_dir():
        raise FileNotFoundError(f"Repository directory does not exist: {repo_root}")

    root = repo_root.resolve()
    scanned: list[ScannedFile] = []

    for current_dir, dirnames, filenames in os.walk(root):
        # Prune ignored folders in-place so os.walk never enters them
        dirnames[:] = sorted(d for d in dirnames if d not in IGNORED_DIRS)

        current_path = Path(current_dir)
        for filename in sorted(filenames):
            file_path = current_path / filename
            language = detect_language(file_path)
            if language is None:
                continue

            content = read_text_file(file_path)
            if content is None or not content.strip():
                continue

            rel_path = file_path.relative_to(root).as_posix()
            line_count = len(content.splitlines())
            scanned.append(
                ScannedFile(
                    abs_path=file_path,
                    rel_path=rel_path,
                    language=language,
                    content=content,
                    line_count=line_count,
                )
            )

    logger.info("Scanned %d supported files in %s", len(scanned), root)
    return scanned
