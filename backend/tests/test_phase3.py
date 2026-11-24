"""Unit tests for Phase 3: Chroma filter building, retriever filtering, summaries, and Gemini service."""

from types import SimpleNamespace

import pytest

from app.rag.retriever import normalize_path_prefix, retrieve_chunks
from app.services import gemini_service
from app.services.gemini_service import GeminiConfigError, GeminiServiceError, generate_text
from app.services.repo_service import build_architecture_summary, build_repo_summary
from app.services.vector_store import build_where_filter


# ── ChromaDB where-filter tests ─────────────────────────────────────────

def test_build_where_filter_single_and_combined() -> None:
    assert build_where_filter(repo_id=5) == {"repo_id": 5}
    assert build_where_filter(repo_id=5, language="Python") == {
        "$and": [{"repo_id": 5}, {"language": "python"}]
    }
    assert build_where_filter(repo_id=5, language="ts", chunk_kind="code") == {
        "$and": [{"repo_id": 5}, {"language": "ts"}, {"chunk_kind": "code"}]
    }


def test_normalize_path_prefix() -> None:
    assert normalize_path_prefix(None) is None
    assert normalize_path_prefix("   ") is None
    assert normalize_path_prefix("./app\\api/") == "app/api/"
    assert normalize_path_prefix("/src/utils") == "src/utils"


# ── Retriever filtering tests (mocked embeddings + vector store) ────────

def test_retriever_filters_by_path_prefix_and_computes_scores(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.rag.retriever.embed_query", lambda q: [0.1, 0.2, 0.3])

    captured_kwargs: dict = {}

    def fake_query_vectors(**kwargs):
        captured_kwargs.update(kwargs)
        return {
            "ids": ["uid_1", "uid_2", "uid_3"],
            "documents": ["doc 1", "doc 2", "doc 3"],
            "metadatas": [
                {
                    "repo_id": 1,
                    "file_path": "tests/test_auth.py",
                    "language": "python",
                    "symbol_name": "test_login",
                    "symbol_type": "function",
                    "start_line": 1,
                    "end_line": 10,
                    "chunk_kind": "code",
                },
                {
                    "repo_id": 1,
                    "file_path": "app/auth/jwt.py",
                    "language": "python",
                    "symbol_name": "generate_token",
                    "symbol_type": "function",
                    "start_line": 15,
                    "end_line": 32,
                    "chunk_kind": "code",
                },
                {
                    "repo_id": 1,
                    "file_path": "app/auth/service.py",
                    "language": "python",
                    "symbol_name": "validate_user",
                    "symbol_type": "method",
                    "parent": "AuthService",
                    "start_line": 20,
                    "end_line": 40,
                    "chunk_kind": "code",
                },
            ],
            "distances": [0.1, 0.2, 0.35],
        }

    monkeypatch.setattr("app.rag.retriever.query_vectors", fake_query_vectors)

    results = retrieve_chunks(
        repo_id=1,
        query="where is jwt token generated?",
        top_k=2,
        language="python",
        path_prefix="app/auth/",
    )

    # Path prefix excludes tests/test_auth.py and forces chunk_kind="code"
    assert captured_kwargs["language"] == "python"
    assert captured_kwargs["chunk_kind"] == "code"
    assert [r.file_path for r in results] == ["app/auth/jwt.py", "app/auth/service.py"]
    # Base score (0.8) + lexical match boost for 'jwt' and 'token' in app/auth/jwt.py / generate_token
    assert results[0].score >= 0.8
    assert results[0].start_line == 15
    assert results[1].parent == "AuthService"


def test_rerank_deprioritizes_tests_and_boilerplate_and_caps_per_file() -> None:
    from app.rag.retriever import rerank_candidates

    candidates = [
        ("u1", "doc", {"file_path": "release-notes.md", "symbol_name": "release-notes.md", "chunk_kind": "code"}, 0.55),
        ("u2", "doc", {"file_path": "tests/test_jwt.py", "symbol_name": "test_jwt", "chunk_kind": "code"}, 0.54),
        ("u3", "doc", {"file_path": "src/auth/jwt.py", "symbol_name": "create_access_token", "chunk_kind": "code"}, 0.50),
        ("u4", "doc", {"file_path": "src/auth/jwt.py", "symbol_name": "verify_token", "chunk_kind": "code"}, 0.49),
        ("u5", "doc", {"file_path": "src/auth/jwt.py", "symbol_name": "decode_token", "chunk_kind": "code"}, 0.48),
        ("u6", "doc", {"file_path": "src/api/login.py", "symbol_name": "login_route", "chunk_kind": "code"}, 0.46),
    ]

    ranked = rerank_candidates("How does create_access_token work in jwt.py?", candidates, top_k=4, max_per_file=2)
    paths = [meta["file_path"] for _, _, meta, _ in ranked]

    # Exact identifier match in src/auth/jwt.py wins #1, capped at 2 chunks from jwt.py,
    # and release-notes.md is pushed behind real source code.
    assert paths[0] == "src/auth/jwt.py"
    assert paths.count("src/auth/jwt.py") == 2
    assert "src/api/login.py" in paths
    assert paths[0] != "release-notes.md"


# ── Summary builder tests ───────────────────────────────────────────────

def test_repo_and_architecture_summary_builders() -> None:
    repo = SimpleNamespace(id=1, name="demo-api", github_url="https://github.com/org/demo-api")
    files = [
        SimpleNamespace(file_path="app/main.py", language="python"),
        SimpleNamespace(file_path="app/auth.py", language="python"),
        SimpleNamespace(file_path="README.md", language="markdown"),
    ]
    chunks = [
        SimpleNamespace(symbol_type="class", symbol_name="AuthService", file_path="app/auth.py", start_line=5, end_line=30),
        SimpleNamespace(symbol_type="function", symbol_name="login", file_path="app/main.py", start_line=10, end_line=22),
    ]

    repo_sum = build_repo_summary(repo, files, chunks, readme_excerpt="# Demo API\nFastAPI service.")
    arch_sum = build_architecture_summary(repo, files, chunks)

    assert "demo-api" in repo_sum
    assert "python: 2" in repo_sum
    assert "FastAPI service." in repo_sum
    assert "app/main.py" in arch_sum
    assert "AuthService" in arch_sum
    assert "login" in arch_sum


# ── Gemini service tests (mocked SDK) ───────────────────────────────────

def test_gemini_raises_config_error_when_key_or_model_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini_service.settings, "GEMINI_API_KEY", "")
    monkeypatch.setattr(gemini_service.settings, "GEMINI_MODEL", "gemini-2.5-flash")
    with pytest.raises(GeminiConfigError, match="GEMINI_API_KEY"):
        generate_text("hello")

    monkeypatch.setattr(gemini_service.settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(gemini_service.settings, "GEMINI_MODEL", "")
    with pytest.raises(GeminiConfigError, match="GEMINI_MODEL"):
        generate_text("hello")


def test_gemini_retries_transient_error_then_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini_service.settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(gemini_service.settings, "GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setattr(gemini_service.time, "sleep", lambda _secs: None)

    calls = {"count": 0}

    class FakeRateLimitError(Exception):
        code = 429

    class FakeModels:
        def generate_content(self, **kwargs):
            calls["count"] += 1
            if calls["count"] == 1:
                raise FakeRateLimitError("429 Too Many Requests")
            return SimpleNamespace(text="JWT tokens are signed in jwt.py.")

    fake_client = SimpleNamespace(models=FakeModels())
    monkeypatch.setattr(gemini_service, "_create_client", lambda api_key, timeout_seconds: fake_client)

    answer = generate_text("explain jwt", max_retries=3)
    assert calls["count"] == 2
    assert "jwt.py" in answer


def test_gemini_does_not_retry_auth_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini_service.settings, "GEMINI_API_KEY", "bad-key")
    monkeypatch.setattr(gemini_service.settings, "GEMINI_MODEL", "gemini-2.5-flash")

    calls = {"count": 0}

    class FakeAuthError(Exception):
        code = 401

    class FakeModels:
        def generate_content(self, **kwargs):
            calls["count"] += 1
            raise FakeAuthError("API key not valid")

    fake_client = SimpleNamespace(models=FakeModels())
    monkeypatch.setattr(gemini_service, "_create_client", lambda api_key, timeout_seconds: fake_client)

    with pytest.raises(GeminiServiceError, match="authentication failed"):
        generate_text("hello", max_retries=3)
    assert calls["count"] == 1


def test_gemini_formats_503_overloaded_cleanly(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(gemini_service.settings, "GEMINI_API_KEY", "fake-key")
    monkeypatch.setattr(gemini_service.settings, "GEMINI_MODEL", "gemini-2.5-flash")
    monkeypatch.setattr(gemini_service.time, "sleep", lambda _secs: None)

    class FakeOverloadError(Exception):
        code = 503

    class FakeModels:
        def generate_content(self, **kwargs):
            raise FakeOverloadError("503 UNAVAILABLE")

    fake_client = SimpleNamespace(models=FakeModels())
    monkeypatch.setattr(gemini_service, "_create_client", lambda api_key, timeout_seconds: fake_client)

    with pytest.raises(GeminiServiceError, match="temporarily overloaded"):
        generate_text("hello", max_retries=2)
