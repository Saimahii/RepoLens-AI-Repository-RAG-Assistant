# RepoLens: project rules (read this before every task)

RepoLens is a full-stack AI Repository RAG Assistant for developers. Users connect a GitHub repo, it is indexed (AST parsing, semantic chunks, embeddings), and users ask natural-language questions about the code. Answers always include an explanation, file paths, line numbers and code snippets.

Keep everything simple, modular, readable and beginner-friendly, but production-like.

## Fixed tech stack (do not swap without asking)

- Frontend: React.js (Create React App), plain CSS, Axios, Monaco Editor (`@monaco-editor/react`)
- Backend: Python FastAPI, SQLAlchemy, MySQL (PyMySQL driver)
- LLM: Gemini API. Use the current official Google Gen AI SDK and check the docs for the current model name. Never hardcode it: read `GEMINI_MODEL` from `.env`.
- Vector DB: ChromaDB (persistent, folder `backend/vector_store/`)
- Embeddings: `sentence-transformers/all-MiniLM-L6-v2`
- Parsing: Python `ast` for .py, Tree-sitter for .js/.ts/.tsx, simple fallback chunking for .java/.go/.md

## Do not use

Docker (for now), Kubernetes, microservices, Redis, Celery, LangGraph or any orchestration framework, distributed infrastructure. Background work uses FastAPI `BackgroundTasks` only.

## Folder structure (keep exactly)

```
repolens/
  backend/
    app/
      api/        routers: repo, chat, files
      services/   repo_service, embedding_service, chat_service
      rag/        retriever.py, pipeline.py
      parsers/    python_parser.py, js_parser.py, fallback_parser.py, chunker.py
      agents/     base_agent, explainer, debugger, bug_finder, architect, router
      database/   db.py (engine, SessionLocal, get_db)
      models/     SQLAlchemy models
      schemas/    Pydantic schemas
      utils/      helpers, file_utils, logger
      prompts/    system + per-agent prompt templates
      config/     settings.py (pydantic-settings, reads .env)
      main.py
    repos/        cloned repositories (git-ignored)
    vector_store/ ChromaDB data (git-ignored)
    requirements.txt
    .env          (never commit; keep .env.example in git)
  frontend/
    src/ components/ styles/ utils/ data/ App.jsx
```

The frontend already exists and works with mock data. Keep its structure and styling. Do not redesign it. Only replace mock data with real API calls, and add Monaco.

## Database tables (keep simple)

- repositories: id, name, github_url, local_path, status (pending, cloning, parsing, embedding, done, failed), error_message, file_count, chunk_count, created_at
- indexed_files: id, repository_id, file_path, language, line_count, created_at
- code_chunks: id, repository_id, file_id, chunk_uid, file_path, language, symbol_name, symbol_type (function, class, method, module), start_line, end_line, imports, parent, content
- chat_sessions: id, repository_id, title, created_at
- messages: id, session_id, role (user or assistant), content, agent, sources_json, created_at

## API contract (frontend depends on these exact shapes)

- `POST /repo/upload` body `{github_url}` returns `{repo_id, status}` (validates URL, clones, registers)
- `POST /repo/index` body `{repo_id}` returns `{repo_id, status}` (starts background parse, embed, store)
- `GET /repo/status/{repo_id}` returns `{status, step, error}` where step is one of cloning, parsing, embedding, done, failed
- `GET /repo/files?repo_id=` returns a nested file tree `[{name, path, type, language, children}]`
- `GET /repo/file?repo_id=&path=` returns `{path, language, content}` (path traversal must be blocked)
- `POST /chat/ask` body `{repo_id, session_id?, question, filters?: {language?, path_prefix?}}` returns `{session_id, agent, answer, sources: [{file_path, start_line, end_line, language, symbol_name, snippet}]}`. The `answer` field is Markdown.
- `GET /chat/sessions?repo_id=` and `GET /chat/history?session_id=` return stored sessions and messages

## RAG pipeline

Question, embed query, vector search (top-k, metadata filters), retrieve chunks with surrounding context lines, add recent chat history (last 6 messages), build prompt (system, agent behavior, repo context, chunks, history, question), Gemini, save to MySQL, return answer plus sources.

Agent routing is keyword-based only: "bug", "issue", "problem" go to Bug Finder. "debug", "error", "fix" go to Debugger. "architecture", "flow", "structure" go to Architecture Explainer. Everything else goes to Code Explainer.

## Code quality rules

- Type hints on all functions. Short docstrings. Beginner-friendly comments that explain why.
- Every external call (git, Gemini, ChromaDB, MySQL, file reads) has error handling with a clear message. No bare `except`. Use the logger, not `print`.
- Ignore folders when scanning: node_modules, dist, build, .git, venv, .venv, __pycache__. Read only .py .js .ts .tsx .java .go .md. Skip files above 1 MB and binary or undecodable files.
- A file that fails to parse must fall back to line-window chunking. It must never crash indexing.
- Secrets live only in `.env`. Add CORS for `http://localhost:3000`.
- If Gemini answers with no relevant chunks, say so honestly. Never invent file paths or line numbers: sources come only from retrieved chunks.
- Re-indexing a repo deletes its old chunks and vectors first.
- Windows is the dev machine (PowerShell). Give Windows commands, and use `pathlib` for paths.

## How to work

1. Work one phase at a time from `BUILD_PLAN.md`. Show an implementation plan first, then build.
2. After each phase: run the code, run its tests, and fix errors before reporting.
3. Add `pytest` tests for parsers, chunker, agent router and file-tree safety.
4. Never claim something works unless you ran it. Report what you could not verify.
5. Stop at the end of each phase with a short summary and the exact commands to run it.
