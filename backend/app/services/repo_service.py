"""Repository service: validate GitHub URLs, clone repos and register them in MySQL."""

from collections import Counter
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

from sqlalchemy import delete, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.config.settings import settings
from app.database.db import SessionLocal
from app.models.code_chunk import CodeChunk
from app.models.indexed_file import IndexedFile
from app.models.repository import Repository
from app.parsers.chunker import chunk_file
from app.services.embedding_service import (
    EmbeddingServiceError,
    build_chunk_embedding_text,
    embed_texts,
)
from app.services.vector_store import VectorStoreError, delete_repo_vectors, upsert_vectors
from app.utils.file_utils import ensure_dir, safe_rmtree, scan_repository_files
from app.utils.helpers import safe_folder_name
from app.utils.logger import get_logger

logger = get_logger(__name__)

# https://github.com/<owner>/<repo> with an optional ".git" and/or trailing slash.
# GitHub owners: letters, digits and single hyphens (max 39 chars).
# Repo names: letters, digits, ".", "-" and "_".
_GITHUB_URL_RE = re.compile(
    r"^https://(?:www\.)?github\.com/"
    r"(?P<owner>[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38})/"
    r"(?P<repo>[A-Za-z0-9._-]+?)"
    r"(?:\.git)?/?$"
)


# ── Errors ──────────────────────────────────────────────────────────────
# Each error carries the HTTP status code the API should return, so the
# router can turn any of them into a clean HTTP response.

class RepoServiceError(Exception):
    """Base error for repository operations."""

    status_code: int = 500

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class InvalidRepoUrlError(RepoServiceError):
    status_code = 400


class RepoNotFoundError(RepoServiceError):
    status_code = 404


class CloneTimeoutError(RepoServiceError):
    status_code = 504


class CloneFailedError(RepoServiceError):
    status_code = 502


class GitNotInstalledError(RepoServiceError):
    status_code = 500


class RepoDatabaseError(RepoServiceError):
    status_code = 500


# ── URL validation ─────────────────────────────────────────────────────

def parse_github_url(url: str) -> tuple[str, str, str]:
    """Validate a GitHub repo URL.

    Returns (owner, repo_name, normalized_url) where normalized_url is
    always "https://github.com/<owner>/<repo>". Raises InvalidRepoUrlError.
    """
    cleaned = url.strip()
    match = _GITHUB_URL_RE.match(cleaned)
    if not match:
        raise InvalidRepoUrlError(
            "Invalid GitHub URL. Use the form https://github.com/<owner>/<repository>."
        )
    owner, repo = match.group("owner"), match.group("repo")
    if repo in {".", ".."}:
        raise InvalidRepoUrlError("Invalid repository name in GitHub URL.")
    return owner, repo, f"https://github.com/{owner}/{repo}"


# ── git clone ──────────────────────────────────────────────────────────

def classify_git_error(stderr: str) -> RepoServiceError:
    """Turn git's error output into a clear, user-facing error."""
    text = stderr.lower()
    not_found_signs = (
        "repository not found",
        "could not read username",   # git wanted a login, so the repo is private or missing
        "authentication failed",
        "terminal prompts disabled",
    )
    if any(sign in text for sign in not_found_signs):
        return RepoNotFoundError(
            "Repository not found or it is private. Only public GitHub repositories are supported."
        )
    if "could not resolve host" in text or "unable to access" in text:
        return CloneFailedError("Could not reach GitHub. Check your internet connection.")
    # Fall back to git's last non-empty line, which usually holds the real reason
    lines = [line.strip() for line in stderr.splitlines() if line.strip()]
    detail = lines[-1] if lines else "unknown git error"
    return CloneFailedError(f"git clone failed: {detail}")


def _kill_process_tree(process: subprocess.Popen) -> None:
    """Stop git and its helper processes (git starts git-remote-https on Windows)."""
    try:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(process.pid)],
                capture_output=True,
                check=False,
            )
        else:
            process.kill()
        process.wait(timeout=10)
    except (OSError, subprocess.SubprocessError) as error:
        logger.warning("Could not stop git process %s: %s", process.pid, error)


def clone_repository(url: str, destination: Path, timeout_seconds: int) -> None:
    """Run `git clone --depth 1 <url> <destination>`.

    Raises a RepoServiceError subclass on any failure.
    """
    # Make sure git never waits for a username/password (it would hang the request)
    env = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GCM_INTERACTIVE": "never"}
    command = [
        "git",
        "-c", "credential.helper=",  # don't open the Windows credential manager popup
        "clone", "--depth", "1", "--quiet",
        url, str(destination),
    ]

    # stderr goes to a temp file instead of a pipe: if git is killed, its child
    # processes could keep a pipe open and block us forever.
    with tempfile.TemporaryFile(mode="w+", encoding="utf-8", errors="replace") as err_file:
        try:
            process = subprocess.Popen(
                command, stdout=subprocess.DEVNULL, stderr=err_file, stdin=subprocess.DEVNULL, env=env
            )
        except FileNotFoundError as error:
            raise GitNotInstalledError(
                "git is not installed or not on PATH. Install Git for Windows and restart the server."
            ) from error
        except OSError as error:
            raise CloneFailedError(f"Could not start git: {error}") from error

        try:
            return_code = process.wait(timeout=timeout_seconds)
        except subprocess.TimeoutExpired as error:
            _kill_process_tree(process)
            raise CloneTimeoutError(
                f"Cloning took longer than {timeout_seconds} seconds and was cancelled. "
                "The repository may be too large."
            ) from error

        err_file.seek(0)
        stderr = err_file.read()

    if return_code != 0:
        logger.warning("git clone failed for %s (exit %s): %s", url, return_code, stderr.strip())
        raise classify_git_error(stderr)


# ── Main entry point ───────────────────────────────────────────────────

def _commit(db: Session, action: str) -> None:
    """Commit, turning database errors into a clear RepoDatabaseError."""
    try:
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        logger.error("Database error while %s: %s", action, error)
        raise RepoDatabaseError(f"Database error while {action}. Check that MySQL is running.") from error


def upload_repository(db: Session, github_url: str) -> Repository:
    """Validate, clone and register a GitHub repository.

    If the repo is already registered and its folder still exists, the
    existing row is returned instead of cloning again.
    """
    owner, name, url = parse_github_url(github_url)
    repos_dir = ensure_dir(settings.repos_dir)

    try:
        repo = db.scalars(select(Repository).where(Repository.github_url == url)).first()
    except SQLAlchemyError as error:
        logger.error("Database lookup failed for %s: %s", url, error)
        raise RepoDatabaseError("Could not read from the database. Check that MySQL is running.") from error

    if repo and repo.status != "failed" and repo.local_path and Path(repo.local_path).is_dir():
        logger.info("Repository %s already registered as id=%s", url, repo.id)
        return repo

    # New repo: insert a row first so we get an id for the folder name
    if repo is None:
        repo = Repository(name=name, github_url=url, local_path="", status="cloning")
        db.add(repo)
        _commit(db, "registering the repository")
        db.refresh(repo)

    destination = repos_dir / safe_folder_name(repo.id, owner, name)
    safe_rmtree(destination)  # remove leftovers from an earlier failed attempt

    repo.local_path = str(destination)
    repo.status = "cloning"
    repo.error_message = None
    _commit(db, "updating the repository status")

    logger.info("Cloning %s into %s", url, destination)
    try:
        clone_repository(url, destination, settings.CLONE_TIMEOUT_SECONDS)
    except RepoServiceError as error:
        safe_rmtree(destination)
        repo.status = "failed"
        repo.error_message = error.message
        try:
            _commit(db, "saving the clone error")
        except RepoDatabaseError:
            logger.error("Could not save failure status for repo id=%s", repo.id)
        raise

    # Cloned but not indexed yet. Indexing (Phase 3) moves it to parsing, embedding, done.
    repo.status = "pending"
    _commit(db, "saving the cloned repository")
    db.refresh(repo)
    logger.info("Cloned %s as repo id=%s", url, repo.id)
    return repo


def parse_and_store_repository(db: Session, repo_id: int) -> tuple[int, int]:
    """Scan, parse, chunk, and store a cloned repository's files and chunks in MySQL.

    Deletes any previous indexed_files and code_chunks for this repo first so
    re-indexing starts from a clean slate. Returns (file_count, chunk_count).
    """
    try:
        repo = db.scalars(select(Repository).where(Repository.id == repo_id)).first()
    except SQLAlchemyError as error:
        logger.error("Database lookup failed for repo id=%s: %s", repo_id, error)
        raise RepoDatabaseError("Could not read repository from the database.") from error

    if repo is None:
        raise RepoNotFoundError(f"Repository id={repo_id} not found.")

    repo_root = Path(repo.local_path)
    if not repo.local_path or not repo_root.is_dir():
        raise RepoServiceError(
            f"Local clone folder for repository id={repo_id} is missing ({repo.local_path}). "
            "Upload the repository again."
        )

    repo.status = "parsing"
    repo.error_message = None
    _commit(db, "marking repository as parsing")

    try:
        # Clean up any old rows before re-indexing (code_chunks first because of FK to indexed_files)
        db.execute(delete(CodeChunk).where(CodeChunk.repository_id == repo.id))
        db.execute(delete(IndexedFile).where(IndexedFile.repository_id == repo.id))
        db.flush()

        scanned_files = scan_repository_files(repo_root)
        total_chunks = 0

        for scanned in scanned_files:
            indexed_file = IndexedFile(
                repository_id=repo.id,
                file_path=scanned.rel_path,
                language=scanned.language,
                line_count=scanned.line_count,
            )
            db.add(indexed_file)
            db.flush()  # populate indexed_file.id for child CodeChunk rows

            chunks = chunk_file(repo.id, scanned)
            for chunk in chunks:
                db.add(
                    CodeChunk(
                        repository_id=repo.id,
                        file_id=indexed_file.id,
                        chunk_uid=chunk.chunk_uid,
                        file_path=chunk.file_path,
                        language=chunk.language,
                        symbol_name=chunk.symbol_name,
                        symbol_type=chunk.symbol_type,
                        start_line=chunk.start_line,
                        end_line=chunk.end_line,
                        imports=chunk.imports,
                        parent=chunk.parent,
                        content=chunk.content,
                    )
                )
            total_chunks += len(chunks)

        repo.file_count = len(scanned_files)
        repo.chunk_count = total_chunks
        _commit(db, "saving parsed files and code chunks")
    except RepoServiceError:
        raise
    except (SQLAlchemyError, OSError) as error:
        db.rollback()
        logger.error("Failed while parsing/storing repo id=%s: %s", repo_id, error)
        repo.status = "failed"
        repo.error_message = f"Parsing failed: {error}"
        try:
            _commit(db, "saving parse failure status")
        except RepoDatabaseError:
            logger.error("Could not persist parse failure for repo id=%s", repo_id)
        raise RepoServiceError(f"Failed to parse and store repository id={repo_id}: {error}") from error

    logger.info(
        "Stored %d files and %d chunks for repo id=%s (%s)",
        repo.file_count,
        repo.chunk_count,
        repo.id,
        repo.name,
    )
    return repo.file_count, repo.chunk_count


# ── Summaries & Background Indexing (Phase 3) ──────────────────────────

_VALID_STATUS_STEPS: dict[str, str] = {
    "pending": "cloning",
    "cloning": "cloning",
    "parsing": "parsing",
    "embedding": "embedding",
    "done": "done",
    "failed": "failed",
}


def build_repo_summary(
    repo: Repository,
    files: list[IndexedFile],
    chunks: list[CodeChunk],
    readme_excerpt: str = "",
) -> str:
    """Build a deterministic repository overview document for high-level semantic search."""
    lang_counts = Counter(f.language for f in files)
    lang_line = ", ".join(f"{lang}: {count}" for lang, count in lang_counts.most_common()) or "none"

    top_dirs = sorted({f.file_path.split("/")[0] for f in files if "/" in f.file_path})
    root_files = sorted(f.file_path for f in files if "/" not in f.file_path)

    lines = [
        f"Repository Summary: {repo.name}",
        f"GitHub URL: {repo.github_url}",
        f"Total indexed files: {len(files)} | Total code chunks: {len(chunks)}",
        f"Languages: {lang_line}",
    ]
    if top_dirs:
        lines.append(f"Top-level directories: {', '.join(top_dirs[:20])}")
    if root_files:
        lines.append(f"Root files: {', '.join(root_files[:20])}")
    if readme_excerpt.strip():
        lines.append("\nREADME overview:\n" + readme_excerpt.strip()[:1800])
    return "\n".join(lines)


def build_architecture_summary(
    repo: Repository,
    files: list[IndexedFile],
    chunks: list[CodeChunk],
) -> str:
    """Build a deterministic architecture summary (modules, key classes/functions, entry points)."""
    # Group files by top-level directory to outline the project layout
    dir_files: dict[str, list[str]] = {}
    for f in files:
        folder = f.file_path.split("/")[0] if "/" in f.file_path else "(root)"
        dir_files.setdefault(folder, []).append(f.file_path)

    classes = [
        f"{c.symbol_name} ({c.file_path}:{c.start_line}-{c.end_line})"
        for c in chunks
        if c.symbol_type == "class" and c.symbol_name
    ]
    functions = [
        f"{c.symbol_name} ({c.file_path}:{c.start_line}-{c.end_line})"
        for c in chunks
        if c.symbol_type == "function" and c.symbol_name
    ]
    entry_candidates = [
        f.file_path
        for f in files
        if Path(f.file_path).name.lower() in {"main.py", "app.py", "server.py", "index.js", "app.js", "app.tsx", "main.go"}
    ]

    lines = [
        f"Architecture Summary: {repo.name}",
        "Module structure:",
    ]
    for folder in sorted(dir_files.keys())[:15]:
        sample_paths = ", ".join(sorted(dir_files[folder])[:6])
        suffix = f" (+{len(dir_files[folder]) - 6} more)" if len(dir_files[folder]) > 6 else ""
        lines.append(f"- {folder}/: {sample_paths}{suffix}")

    if entry_candidates:
        lines.append(f"\nLikely entry points: {', '.join(entry_candidates[:10])}")
    if classes:
        lines.append("\nKey classes:\n- " + "\n- ".join(classes[:25]))
    if functions:
        lines.append("\nKey top-level functions:\n- " + "\n- ".join(functions[:25]))
    return "\n".join(lines)


def _read_readme_excerpt(repo_root: Path) -> str:
    """Read the first part of README.md (or README) if present in the cloned repo."""
    for candidate in ("README.md", "readme.md", "README.MD", "README"):
        readme_path = repo_root / candidate
        if readme_path.is_file():
            try:
                return readme_path.read_text(encoding="utf-8-sig", errors="replace")[:2000]
            except OSError:
                return ""
    return ""


def get_repo_status(db: Session, repo_id: int) -> tuple[str, str, str | None]:
    """Return (status, step, error_message) for GET /repo/status/{repo_id}."""
    try:
        repo = db.scalars(select(Repository).where(Repository.id == repo_id)).first()
    except SQLAlchemyError as error:
        logger.error("Status lookup failed for repo id=%s: %s", repo_id, error)
        raise RepoDatabaseError("Could not read repository status from MySQL.") from error

    if repo is None:
        raise RepoNotFoundError(f"Repository id={repo_id} not found.")

    step = _VALID_STATUS_STEPS.get(repo.status, "failed")
    return repo.status, step, repo.error_message


def prepare_repo_for_indexing(db: Session, repo_id: int) -> Repository:
    """Validate that a repo is ready to index and mark its status as 'parsing'."""
    try:
        repo = db.scalars(select(Repository).where(Repository.id == repo_id)).first()
    except SQLAlchemyError as error:
        logger.error("Lookup failed before indexing repo id=%s: %s", repo_id, error)
        raise RepoDatabaseError("Could not read repository from MySQL.") from error

    if repo is None:
        raise RepoNotFoundError(f"Repository id={repo_id} not found.")

    if not repo.local_path or not Path(repo.local_path).is_dir():
        raise RepoServiceError(
            f"Cloned folder for repository id={repo_id} is missing. Upload the repository again."
        )

    repo.status = "parsing"
    repo.error_message = None
    _commit(db, "starting repository indexing")
    db.refresh(repo)
    return repo


def run_index_pipeline(repo_id: int) -> None:
    """Background indexing pipeline: clean old vectors -> parse/store -> embed -> upsert -> done.

    Opens and closes its own DB session so it runs safely inside FastAPI BackgroundTasks.
    """
    db = SessionLocal()
    try:
        # 1. Remove any stale ChromaDB vectors for this repo first (safe re-indexing)
        delete_repo_vectors(repo_id)

        # 2. Scan, parse, chunk, and persist indexed_files + code_chunks in MySQL
        parse_and_store_repository(db, repo_id)

        repo = db.scalars(select(Repository).where(Repository.id == repo_id)).first()
        if repo is None:
            raise RepoNotFoundError(f"Repository id={repo_id} disappeared during indexing.")

        # 3. Transition status to embedding
        repo.status = "embedding"
        repo.error_message = None
        _commit(db, "marking repository as embedding")

        files = list(db.scalars(select(IndexedFile).where(IndexedFile.repository_id == repo_id)).all())
        chunks = list(db.scalars(select(CodeChunk).where(CodeChunk.repository_id == repo_id)).all())

        ids: list[str] = []
        documents: list[str] = []
        metadatas: list[dict[str, str | int | float | bool]] = []

        for chunk in chunks:
            ids.append(chunk.chunk_uid)
            documents.append(
                build_chunk_embedding_text(
                    file_path=chunk.file_path,
                    language=chunk.language,
                    symbol_type=chunk.symbol_type,
                    symbol_name=chunk.symbol_name,
                    parent=chunk.parent,
                    content=chunk.content,
                )
            )
            metadatas.append(
                {
                    "repo_id": int(repo.id),
                    "file_path": chunk.file_path,
                    "language": chunk.language,
                    "symbol_name": chunk.symbol_name or "",
                    "symbol_type": chunk.symbol_type,
                    "parent": chunk.parent or "",
                    "start_line": int(chunk.start_line),
                    "end_line": int(chunk.end_line),
                    "chunk_kind": "code",
                }
            )

        # 4. Add repository summary and architecture summary embeddings
        readme_excerpt = _read_readme_excerpt(Path(repo.local_path)) if repo.local_path else ""
        repo_summary_text = build_repo_summary(repo, files, chunks, readme_excerpt=readme_excerpt)
        arch_summary_text = build_architecture_summary(repo, files, chunks)

        ids.extend([f"repo_{repo.id}_summary", f"repo_{repo.id}_architecture"])
        documents.extend([repo_summary_text, arch_summary_text])
        metadatas.extend(
            [
                {
                    "repo_id": int(repo.id),
                    "file_path": "__repo_summary__",
                    "language": "markdown",
                    "symbol_name": "Repository Summary",
                    "symbol_type": "module",
                    "parent": "",
                    "start_line": 1,
                    "end_line": max(1, len(repo_summary_text.splitlines())),
                    "chunk_kind": "repo_summary",
                },
                {
                    "repo_id": int(repo.id),
                    "file_path": "__architecture_summary__",
                    "language": "markdown",
                    "symbol_name": "Architecture Summary",
                    "symbol_type": "module",
                    "parent": "",
                    "start_line": 1,
                    "end_line": max(1, len(arch_summary_text.splitlines())),
                    "chunk_kind": "arch_summary",
                },
            ]
        )

        # 5. Batch-encode and persist to ChromaDB
        embeddings = embed_texts(documents)
        upsert_vectors(ids=ids, embeddings=embeddings, documents=documents, metadatas=metadatas)

        # 6. Mark repository indexing complete
        repo.status = "done"
        repo.error_message = None
        _commit(db, "marking repository indexing as done")
        logger.info(
            "Indexing complete for repo id=%s (%s): %d files, %d code chunks + 2 summaries embedded.",
            repo.id,
            repo.name,
            len(files),
            len(chunks),
        )
    except (RepoServiceError, EmbeddingServiceError, VectorStoreError, SQLAlchemyError, OSError) as error:
        logger.error("Background indexing failed for repo id=%s: %s", repo_id, error)
        db.rollback()
        try:
            repo = db.scalars(select(Repository).where(Repository.id == repo_id)).first()
            if repo is not None:
                repo.status = "failed"
                repo.error_message = str(error)
                db.commit()
        except SQLAlchemyError as save_error:
            logger.error("Could not save failed status for repo id=%s: %s", repo_id, save_error)
    finally:
        db.close()
