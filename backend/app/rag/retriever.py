"""Semantic retriever: embeds queries, queries ChromaDB with filters, re-ranks, hydrates from MySQL."""

from dataclasses import dataclass
import re

from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.code_chunk import CodeChunk
from app.services.embedding_service import embed_query
from app.services.vector_store import query_vectors
from app.utils.logger import get_logger

logger = get_logger(__name__)

# Stopwords ignored when extracting identifier/path tokens from a user question
_QUERY_STOPWORDS: frozenset[str] = frozenset(
    {
        "the", "and", "for", "with", "that", "this", "from", "are", "how", "does",
        "what", "where", "when", "why", "who", "can", "you", "explain", "show",
        "find", "code", "file", "files", "repo", "repository", "function", "class",
        "method", "work", "works", "used", "using", "into", "about", "there",
    }
)

_BOILERPLATE_NAMES: frozenset[str] = frozenset(
    {
        "changelog.md",
        "release-notes.md",
        "contributing.md",
        "code_of_conduct.md",
        "security.md",
        "license.md",
        "pull_request_template.md",
    }
)

_TEST_QUERY_RE = re.compile(r"\b(tests?|pytest|jest|unittest|spec|mock|coverage)\b", re.IGNORECASE)
_META_DOC_QUERY_RE = re.compile(
    r"\b(changelog|release[- ]notes|contributing|issue template|pull request|github actions|workflow)\b",
    re.IGNORECASE,
)
_ARCH_QUERY_RE = re.compile(
    r"\b(architecture|structure|overview|summarize|summary|layout|folder|modules?|flow)\b",
    re.IGNORECASE,
)
_TOKEN_RE = re.compile(r"[A-Za-z0-9_./-]{3,}")

MAX_CHUNKS_PER_FILE: int = 2


@dataclass
class RetrievedChunk:
    """One retrieved chunk returned by the vector search pipeline."""

    chunk_uid: str
    file_path: str
    language: str
    symbol_name: str | None
    symbol_type: str
    start_line: int
    end_line: int
    content: str
    score: float
    parent: str | None = None
    imports: str | None = None
    chunk_kind: str = "code"  # "code", "repo_summary", or "arch_summary"


def normalize_path_prefix(path_prefix: str | None) -> str | None:
    """Normalize a user-provided path prefix to POSIX format without leading slashes."""
    if not path_prefix:
        return None
    cleaned = path_prefix.strip().replace("\\", "/").lstrip("./").lstrip("/")
    return cleaned or None


def _extract_query_tokens(query: str) -> set[str]:
    """Extract meaningful identifier and path tokens from a query for lexical boosting."""
    tokens: set[str] = set()
    for raw in _TOKEN_RE.findall(query):
        # Split camelCase / snake_case / paths into searchable pieces while keeping the whole token
        lower = raw.lower().strip("./-")
        if len(lower) >= 3 and lower not in _QUERY_STOPWORDS:
            tokens.add(lower)
        for piece in re.split(r"[_/.-]+", lower):
            if len(piece) >= 3 and piece not in _QUERY_STOPWORDS:
                tokens.add(piece)
    return tokens


def _is_test_path(file_path: str) -> bool:
    """Return True if a relative POSIX path looks like a test file."""
    lower = file_path.lower()
    parts = lower.split("/")
    filename = parts[-1] if parts else ""
    if any(p in {"test", "tests", "__tests__", "spec", "specs"} for p in parts[:-1]):
        return True
    return (
        filename.startswith("test_")
        or filename.endswith("_test.py")
        or filename.endswith("_test.go")
        or ".test." in filename
        or ".spec." in filename
    )


def _is_boilerplate_path(file_path: str) -> bool:
    """Return True for repo housekeeping docs (.github templates, changelogs, release notes)."""
    lower = file_path.lower()
    parts = lower.split("/")
    filename = parts[-1] if parts else ""
    return ".github" in parts or filename in _BOILERPLATE_NAMES


def rerank_candidates(
    query: str,
    candidates: list[tuple[str, str, dict, float]],
    top_k: int,
    max_per_file: int = MAX_CHUNKS_PER_FILE,
) -> list[tuple[str, str, dict, float]]:
    """Apply lightweight lexical & structural re-ranking + per-file diversity cap.

    - Boosts chunks whose symbol_name or file_path match query identifiers.
    - Gently down-weights test files and .github/changelog boilerplate unless asked about.
    - Boosts repo/architecture summaries on architecture/overview questions.
    - Caps results to at most `max_per_file` chunks per file (unless needed to fill top_k).
    """
    if not candidates:
        return []

    query_tokens = _extract_query_tokens(query)
    wants_tests = bool(_TEST_QUERY_RE.search(query))
    wants_meta_docs = bool(_META_DOC_QUERY_RE.search(query))
    wants_arch = bool(_ARCH_QUERY_RE.search(query))

    scored: list[tuple[float, str, str, dict, float]] = []
    for uid, doc, meta, base_score in candidates:
        file_path = str(meta.get("file_path") or "")
        symbol_name = str(meta.get("symbol_name") or "")
        chunk_kind = str(meta.get("chunk_kind") or "code")

        adjusted = base_score

        # 1. Exact/partial identifier match in symbol name or file path
        if chunk_kind == "code" and query_tokens:
            haystack = f"{file_path.lower()} {symbol_name.lower()}"
            matches = sum(1 for tok in query_tokens if tok in haystack)
            adjusted += min(0.16, matches * 0.04)

        # 2. De-prioritize boilerplate & test files unless the user explicitly asks for them
        if chunk_kind == "code":
            if not wants_meta_docs and _is_boilerplate_path(file_path):
                adjusted -= 0.14
            if not wants_tests and _is_test_path(file_path):
                adjusted -= 0.08
        elif wants_arch:
            # 3. Surface repository & architecture summaries on architecture/overview questions
            adjusted += 0.12

        scored.append((round(adjusted, 4), uid, doc, meta, base_score))

    scored.sort(key=lambda item: item[0], reverse=True)

    # Enforce per-file diversity so one large file cannot monopolize all top-k slots
    selected: list[tuple[str, str, dict, float]] = []
    overflow: list[tuple[str, str, dict, float]] = []
    per_file_counts: dict[str, int] = {}

    for adj_score, uid, doc, meta, _ in scored:
        file_path = str(meta.get("file_path") or "")
        count = per_file_counts.get(file_path, 0)
        if count < max_per_file:
            per_file_counts[file_path] = count + 1
            selected.append((uid, doc, meta, adj_score))
            if len(selected) >= top_k:
                break
        else:
            overflow.append((uid, doc, meta, adj_score))

    # If the repo has very few distinct files, fill remaining slots from overflow
    if len(selected) < top_k and overflow:
        selected.extend(overflow[: top_k - len(selected)])

    return selected


def retrieve_chunks(
    repo_id: int,
    query: str,
    top_k: int = 6,
    language: str | None = None,
    path_prefix: str | None = None,
    include_summaries: bool = True,
    db: Session | None = None,
) -> list[RetrievedChunk]:
    """Retrieve the top-k most relevant chunks for a question from ChromaDB.

    Supports filtering by repo_id, language, and path_prefix, applies lightweight
    hybrid re-ranking + per-file diversity, and hydrates full chunks from MySQL.
    """
    if top_k <= 0 or not query.strip():
        return []

    norm_prefix = normalize_path_prefix(path_prefix)
    norm_language = language.lower().strip() if language and language.strip() else None

    # Summaries are repo-wide, so skip them when the caller filters to a specific path or language
    want_summaries = include_summaries and norm_prefix is None and norm_language is None
    chunk_kind_filter = None if want_summaries else "code"

    # Over-fetch candidates so re-ranking, path_prefix filtering, and per-file diversity work well
    fetch_k = max(top_k * 5, 30) if norm_prefix else max(top_k * 4, 24)

    query_embedding = embed_query(query)
    raw = query_vectors(
        query_embedding=query_embedding,
        repo_id=repo_id,
        n_results=fetch_k,
        language=norm_language,
        chunk_kind=chunk_kind_filter,
    )

    ids = raw["ids"]
    docs = raw["documents"]
    metas = raw["metadatas"]
    dists = raw["distances"]

    if not ids:
        return []

    # Filter by path_prefix (if provided) and convert cosine distance -> similarity score
    candidates: list[tuple[str, str, dict, float]] = []
    for uid, doc, meta, dist in zip(ids, docs, metas, dists):
        meta = meta or {}
        file_path = str(meta.get("file_path") or "")
        if norm_prefix and not file_path.startswith(norm_prefix):
            continue
        score = round(1.0 - float(dist), 4)
        candidates.append((uid, doc or "", meta, score))

    if not candidates:
        return []

    selected = rerank_candidates(query=query, candidates=candidates, top_k=top_k)

    # Hydrate code chunks from MySQL when a DB session is available
    mysql_by_uid: dict[str, CodeChunk] = {}
    if db is not None:
        code_uids = [uid for uid, _, meta, _ in selected if meta.get("chunk_kind", "code") == "code"]
        if code_uids:
            try:
                rows = db.scalars(
                    select(CodeChunk).where(
                        CodeChunk.repository_id == repo_id,
                        CodeChunk.chunk_uid.in_(code_uids),
                    )
                ).all()
                mysql_by_uid = {row.chunk_uid: row for row in rows}
            except SQLAlchemyError as error:
                logger.warning("Could not hydrate chunks from MySQL (falling back to Chroma text): %s", error)

    results: list[RetrievedChunk] = []
    for uid, doc, meta, score in selected:
        chunk_kind = str(meta.get("chunk_kind") or "code")
        db_row = mysql_by_uid.get(uid)
        if db_row is not None:
            results.append(
                RetrievedChunk(
                    chunk_uid=db_row.chunk_uid,
                    file_path=db_row.file_path,
                    language=db_row.language,
                    symbol_name=db_row.symbol_name,
                    symbol_type=db_row.symbol_type,
                    start_line=db_row.start_line,
                    end_line=db_row.end_line,
                    content=db_row.content,
                    score=score,
                    parent=db_row.parent,
                    imports=db_row.imports,
                    chunk_kind=chunk_kind,
                )
            )
        else:
            results.append(
                RetrievedChunk(
                    chunk_uid=uid,
                    file_path=str(meta.get("file_path") or ""),
                    language=str(meta.get("language") or "markdown"),
                    symbol_name=str(meta.get("symbol_name") or "") or None,
                    symbol_type=str(meta.get("symbol_type") or "module"),
                    start_line=int(meta.get("start_line") or 1),
                    end_line=int(meta.get("end_line") or 1),
                    content=doc,
                    score=score,
                    parent=str(meta.get("parent") or "") or None,
                    imports=None,
                    chunk_kind=chunk_kind,
                )
            )

    return results
