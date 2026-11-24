"""Unit tests for the RAG pipeline: follow-up query building, grounded sources, and empty-chunk honesty."""

from types import SimpleNamespace

import pytest

from app.rag.pipeline import build_retrieval_query, chunks_to_sources, run_rag_pipeline
from app.rag.retriever import RetrievedChunk
from app.schemas.chat import ChatFilters


def test_build_retrieval_query_adds_previous_user_turn() -> None:
    history = [
        {"role": "user", "content": "How does authentication work?"},
        {"role": "assistant", "content": "It uses JWT tokens."},
    ]
    enriched = build_retrieval_query("Where is the JWT generated?", history)
    assert "Where is the JWT generated?" in enriched
    assert "How does authentication work?" in enriched


def test_chunks_to_sources_excludes_summaries_and_deduplicates() -> None:
    chunks = [
        RetrievedChunk(
            chunk_uid="sum1",
            file_path="__repo_summary__",
            language="markdown",
            symbol_name="Repository Summary",
            symbol_type="module",
            start_line=1,
            end_line=20,
            content="Summary text",
            score=0.9,
            chunk_kind="repo_summary",
        ),
        RetrievedChunk(
            chunk_uid="c1",
            file_path="app/auth/jwt.py",
            language="python",
            symbol_name="generate_token",
            symbol_type="function",
            start_line=15,
            end_line=32,
            content="def generate_token(user_id): ...",
            score=0.85,
            chunk_kind="code",
        ),
        # Duplicate range should be deduplicated
        RetrievedChunk(
            chunk_uid="c1_dup",
            file_path="app/auth/jwt.py",
            language="python",
            symbol_name="generate_token",
            symbol_type="function",
            start_line=15,
            end_line=32,
            content="def generate_token(user_id): ...",
            score=0.80,
            chunk_kind="code",
        ),
    ]

    sources = chunks_to_sources(chunks)
    assert len(sources) == 1
    assert sources[0].file_path == "app/auth/jwt.py"
    assert (sources[0].start_line, sources[0].end_line) == (15, 32)
    assert sources[0].symbol_name == "generate_token"


def test_rag_pipeline_returns_honest_message_when_no_chunks_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.rag.pipeline.retrieve_chunks", lambda **kwargs: [])

    # Gemini must NOT be called when nothing was retrieved
    def fail_if_called(**kwargs):
        raise AssertionError("Gemini should not be called when zero chunks are retrieved")

    monkeypatch.setattr("app.agents.base_agent.generate_text", fail_if_called)

    repo = SimpleNamespace(id=1, name="demo", github_url="https://github.com/a/b", file_count=5, chunk_count=10)
    result = run_rag_pipeline(
        db=None,  # type: ignore[arg-type]
        repo=repo,  # type: ignore[arg-type]
        question="Explain the payment module",
        history=[],
        filters=ChatFilters(language="go"),
    )

    assert result.agent == "explainer"
    assert result.sources == []
    assert "could not find any relevant indexed code chunks" in result.answer.lower()
    assert "filter" in result.answer.lower()


def test_rag_pipeline_passes_history_and_returns_only_retrieved_sources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieved = [
        RetrievedChunk(
            chunk_uid="c1",
            file_path="app/auth/jwt.py",
            language="python",
            symbol_name="generate_token",
            symbol_type="function",
            start_line=15,
            end_line=32,
            content="def generate_token(user_id):\n    return jwt.encode(...)",
            score=0.91,
            chunk_kind="code",
        ),
    ]
    monkeypatch.setattr("app.rag.pipeline.retrieve_chunks", lambda **kwargs: retrieved)

    captured_prompt: dict[str, str] = {}

    def fake_generate_text(prompt: str, system_instruction: str | None = None, temperature: float = 0.2) -> str:
        captured_prompt["prompt"] = prompt
        captured_prompt["system"] = system_instruction or ""
        return "JWT tokens are generated in `app/auth/jwt.py` lines 15-32."

    monkeypatch.setattr("app.agents.base_agent.generate_text", fake_generate_text)

    repo = SimpleNamespace(id=1, name="demo", github_url="https://github.com/a/b", file_count=5, chunk_count=10)
    history = [
        {"role": "user", "content": "How does auth work?"},
        {"role": "assistant", "content": "Auth uses JWT middleware."},
    ]

    result = run_rag_pipeline(
        db=None,  # type: ignore[arg-type]
        repo=repo,  # type: ignore[arg-type]
        question="Where is the JWT generated?",
        history=history,
    )

    assert result.agent == "explainer"
    assert "How does auth work?" in captured_prompt["prompt"]
    assert "app/auth/jwt.py" in captured_prompt["prompt"]
    assert "Code Explainer" in captured_prompt["system"]
    assert len(result.sources) == 1
    assert result.sources[0].file_path == "app/auth/jwt.py"
    assert result.sources[0].start_line == 15
    assert result.sources[0].end_line == 32
