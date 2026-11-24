"""Repository file tree builder and path-traversal-safe file reader."""

from pathlib import Path, PurePosixPath
from typing import Any, Sequence

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.indexed_file import IndexedFile
from app.models.repository import Repository
from app.schemas.files import FileContentResponse, FileTreeNode
from app.utils.file_utils import IGNORED_DIRS, detect_language, read_text_file
from app.utils.logger import get_logger

logger = get_logger(__name__)


class FileServiceError(Exception):
    """Base error for file-tree and file-read operations."""

    status_code: int = 500

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class FilePathTraversalError(FileServiceError):
    """Raised when a requested file path tries to escape the repository root."""

    def __init__(self, message: str = "Invalid file path: path traversal is not allowed.") -> None:
        super().__init__(message, status_code=400)


class FileNotFoundInRepoError(FileServiceError):
    """Raised when the repository or requested file does not exist."""

    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


def build_file_tree(entries: Sequence[tuple[str, str]]) -> list[FileTreeNode]:
    """Turn a flat list of (rel_path, language) tuples into a sorted nested file tree.

    Folders come before files, and each level is sorted alphabetically.
    """
    root_map: dict[str, Any] = {}

    for rel_path, language in entries:
        cleaned = rel_path.replace("\\", "/").strip("/")
        if not cleaned:
            continue
        parts = [p for p in cleaned.split("/") if p and p != "."]
        if not parts:
            continue

        current = root_map
        built_parts: list[str] = []
        for idx, part in enumerate(parts):
            built_parts.append(part)
            is_file = idx == len(parts) - 1
            node_path = "/".join(built_parts)

            if is_file:
                current[part] = {
                    "name": part,
                    "path": node_path,
                    "type": "file",
                    "language": language,
                    "children": {},
                }
            else:
                if part not in current or current[part]["type"] != "folder":
                    current[part] = {
                        "name": part,
                        "path": node_path,
                        "type": "folder",
                        "language": None,
                        "children": {},
                    }
                current = current[part]["children"]

    def _to_nodes(level: dict[str, Any]) -> list[FileTreeNode]:
        items = sorted(
            level.values(),
            key=lambda item: (0 if item["type"] == "folder" else 1, item["name"].lower()),
        )
        return [
            FileTreeNode(
                name=item["name"],
                path=item["path"],
                type=item["type"],
                language=item["language"],
                children=_to_nodes(item["children"]) if item["type"] == "folder" else [],
            )
            for item in items
        ]

    return _to_nodes(root_map)


def resolve_safe_repo_path(repo_root: Path, requested_path: str) -> tuple[Path, str]:
    """Validate and resolve a relative path strictly inside `repo_root`.

    Blocks `..`, absolute paths, Windows drive prefixes, null bytes, ignored
    folders (such as `.git`), and symlinks escaping `repo_root`.
    """
    if not requested_path or not requested_path.strip():
        raise FilePathTraversalError("File path cannot be empty.")

    raw = requested_path.strip()
    if "\x00" in raw:
        raise FilePathTraversalError("Invalid null byte in file path.")

    # Reject Windows drive letters (e.g. C:\...) or UNC paths (\\server\...)
    if raw.startswith(("/", "\\")) or (len(raw) >= 2 and raw[1] == ":"):
        raise FilePathTraversalError("Absolute paths are not allowed.")

    posix_str = raw.replace("\\", "/")
    posix = PurePosixPath(posix_str)
    parts = [p for p in posix.parts if p != "."]

    if not parts or any(p == ".." for p in parts):
        raise FilePathTraversalError("Path traversal ('..') is not allowed.")

    if any(p in IGNORED_DIRS for p in parts):
        raise FilePathTraversalError("Access to ignored or internal folders is not allowed.")

    resolved_root = repo_root.resolve()
    candidate = (resolved_root / Path(*parts)).resolve()

    # Final safety barrier: catches symlinks or OS path tricks escaping repo_root
    if not candidate.is_relative_to(resolved_root) or candidate == resolved_root:
        raise FilePathTraversalError("Resolved path escapes the repository directory.")

    return candidate, "/".join(parts)


def get_repo_file_tree(db: Session, repo_id: int) -> list[FileTreeNode]:
    """Fetch indexed_files for a repository and return a nested file tree."""
    try:
        repo = db.scalars(select(Repository).where(Repository.id == repo_id)).first()
    except SQLAlchemyError as error:
        logger.error("Failed to fetch repository id=%s: %s", repo_id, error)
        raise FileServiceError("Could not read repository from MySQL.", status_code=500) from error

    if repo is None:
        raise FileNotFoundInRepoError(f"Repository id={repo_id} not found.")

    try:
        files = db.scalars(
            select(IndexedFile)
            .where(IndexedFile.repository_id == repo_id)
            .order_by(IndexedFile.file_path.asc())
        ).all()
    except SQLAlchemyError as error:
        logger.error("Failed to load indexed files for repo_id=%s: %s", repo_id, error)
        raise FileServiceError("Could not load repository file list from MySQL.", status_code=500) from error

    return build_file_tree([(f.file_path, f.language) for f in files])


def read_repo_file(db: Session, repo_id: int, requested_path: str) -> FileContentResponse:
    """Safely read a single source file from a cloned repository."""
    try:
        repo = db.scalars(select(Repository).where(Repository.id == repo_id)).first()
    except SQLAlchemyError as error:
        logger.error("Failed to fetch repository id=%s: %s", repo_id, error)
        raise FileServiceError("Could not read repository from MySQL.", status_code=500) from error

    if repo is None:
        raise FileNotFoundInRepoError(f"Repository id={repo_id} not found.")

    repo_root = Path(repo.local_path)
    if not repo.local_path or not repo_root.is_dir():
        raise FileNotFoundInRepoError(
            f"Cloned directory for repository id={repo_id} is missing on disk."
        )

    safe_path, norm_rel_path = resolve_safe_repo_path(repo_root, requested_path)
    if not safe_path.is_file():
        raise FileNotFoundInRepoError(f"File '{norm_rel_path}' not found in repository id={repo_id}.")

    content = read_text_file(safe_path)
    if content is None:
        raise FileServiceError(
            f"File '{norm_rel_path}' cannot be displayed (exceeds 1 MB, binary, or non-UTF-8).",
            status_code=400,
        )

    language = detect_language(safe_path) or "plaintext"
    return FileContentResponse(path=norm_rel_path, language=language, content=content)
