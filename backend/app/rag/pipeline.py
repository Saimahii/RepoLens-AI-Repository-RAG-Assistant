"""End-to-end RAG pipeline: route agent -> retrieve chunks -> call Gemini -> return grounded sources."""

from dataclasses import dataclass
from typing import Sequence

from sqlalchemy.orm import Session

from app.agents.router import route_agent
from app.models.repository import Repository
from app.rag.retriever import RetrievedChunk, retrieve_chunks
from app.schemas.chat import ChatFilters, SourceItem
from app.utils.logger import get_logger

logger = get_logger(__name__)

DEFAULT_TOP_K: int = 6
MAX_SNIPPET_CHARS: int = 2000


@dataclass
class RagResult:
    """Output of the RAG pipeline ready to persist and return to the client."""

    agent: str
    answer: str
    sources: list[SourceItem]


def build_retrieval_query(question: str, history: Sequence[dict[str, str]]) -> str:
    """Combine a follow-up question with the previous user message for stronger retrieval."""
    cleaned = question.strip()
    if not history:
        return cleaned

    last_user_message = ""
    for msg in reversed(history):
        if msg.get("role") == "user" and (msg.get("content") or "").strip():
            last_user_message = msg["content"].strip()
            break

    if not last_user_message or last_user_message.lower() == cleaned.lower():
        return cleaned

    # Keep the retrieval query focused so follow-ups inherit the prior topic
    return f"{cleaned}\nContext: {last_user_message[:300]}"


def chunks_to_sources(code_chunks: Sequence[RetrievedChunk]) -> list[SourceItem]:
    """Turn retrieved code chunks into deduplicated, strictly grounded SourceItem objects."""
    sources: list[SourceItem] = []
    seen: set[tuple[str, int, int]] = set()

    for chunk in code_chunks:
        if chunk.chunk_kind != "code" or not chunk.file_path:
            continue
        key = (chunk.file_path, chunk.start_line, chunk.end_line)
        if key in seen:
            continue
        seen.add(key)

        snippet = chunk.content
        if len(snippet) > MAX_SNIPPET_CHARS:
            snippet = snippet[: MAX_SNIPPET_CHARS - 3] + "..."

        sources.append(
            SourceItem(
                file_path=chunk.file_path,
                start_line=chunk.start_line,
                end_line=chunk.end_line,
                language=chunk.language,
                symbol_name=chunk.symbol_name,
                snippet=snippet,
            )
        )

    return sources


def build_repo_context(repo: Repository) -> str:
    """Summarize basic repository metadata for the prompt."""
    return (
        f"Repository: {repo.name}\n"
        f"GitHub URL: {repo.github_url}\n"
        f"Indexed files: {repo.file_count} | Indexed chunks: {repo.chunk_count}"
    )


def run_rag_pipeline(
    db: Session,
    repo: Repository,
    question: str,
    history: Sequence[dict[str, str]],
    filters: ChatFilters | None = None,
    top_k: int = DEFAULT_TOP_K,
) -> RagResult:
    """Execute the full RepoLens RAG flow for one user question."""
    agent = route_agent(question)
    retrieval_query = build_retrieval_query(question, history)

    language = filters.language if filters else None
    path_prefix = filters.path_prefix if filters else None

    retrieved = retrieve_chunks(
        repo_id=repo.id,
        query=retrieval_query,
        top_k=top_k,
        language=language,
        path_prefix=path_prefix,
        include_summaries=True,
        db=db,
    )

    code_chunks = [c for c in retrieved if c.chunk_kind == "code"]
    summary_chunks = [c for c in retrieved if c.chunk_kind != "code"]

    # Honest fallback when nothing matched (e.g. overly narrow filter or empty repo)
    if not code_chunks and not summary_chunks:
        filter_note = ""
        if language or path_prefix:
            filter_note = " Try clearing or broadening your language/path filters."
        honest_answer = (
            "I could not find any relevant indexed code chunks in this repository to answer your question."
            f"{filter_note}"
        )
        logger.info("No relevant chunks retrieved for repo_id=%s question=%r", repo.id, question[:80])
        return RagResult(agent=agent.name, answer=honest_answer, sources=[])

    logger.info(
        "Running agent=%s for repo_id=%s with %d code chunks, %d summaries, %d history msgs",
        agent.name,
        repo.id,
        len(code_chunks),
        len(summary_chunks),
        len(history),
    )
    answer = agent.run(
        repo_context=build_repo_context(repo),
        code_chunks=code_chunks,
        summary_chunks=summary_chunks,
        history=history,
        question=question,
    )
    sources = chunks_to_sources(code_chunks)
    return RagResult(agent=agent.name, answer=answer, sources=sources)
