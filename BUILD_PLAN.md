# RepoLens: build plan

Follow the rules in AGENTS.md. Do one phase at a time. At the end of each phase, run it, test it, and stop with a summary and the exact commands to run.

## Phase 1: backend foundation

- Create the backend folder structure from AGENTS.md
- `requirements.txt` (pin versions that install cleanly on Windows)
- `.env.example` with: `DATABASE_URL`, `GEMINI_API_KEY`, `GEMINI_MODEL`, `CHROMA_PATH`, `REPOS_PATH`
- `config/settings.py` using pydantic-settings
- `database/db.py` and all 5 SQLAlchemy models, tables created on startup
- `main.py` with CORS for http://localhost:3000 and a `GET /health` endpoint
- `POST /repo/upload`: validate a GitHub URL, clone with `git clone --depth 1` into `repos/`, save metadata in MySQL, handle private or missing repos and timeouts with clear errors
- Done when: `uvicorn app.main:app --reload` starts, `/docs` loads, and uploading a small public repo creates a row in MySQL and a folder in `repos/`

## Phase 2: parsing and chunking

- File scanner with the ignore rules and size limit
- `python_parser.py` (ast): classes, functions, methods, imports, docstrings, decorators and FastAPI/Flask routes
- `js_parser.py` (Tree-sitter): functions, classes, React components, imports, routes
- `fallback_parser.py` for .java, .go, .md and any file that fails to parse (line windows with overlap)
- `chunker.py`: one chunk per function or class or method, with context lines, metadata, and a stable `chunk_uid`. Split very large chunks sensibly.
- Save indexed_files and code_chunks to MySQL
- Done when: pytest passes on sample files and a real repo produces sensible chunks with correct line numbers

## Phase 3: embeddings, vector search, Gemini

- `embedding_service.py`: load MiniLM once, batch encode
- ChromaDB persistent collection with metadata (repo_id, file_path, language, symbol_name, start_line, end_line)
- `rag/retriever.py`: top-k similarity search with repo_id, language and path filters
- Repository summary and architecture summary embeddings
- `POST /repo/index` with BackgroundTasks, `GET /repo/status/{repo_id}`, re-index cleanup
- Gemini service with retries, timeout and clean error messages
- Done when: indexing a repo reaches status "done" and a test query returns relevant chunks

## Phase 4: agents and chat

- Prompt templates in `prompts/`
- Four agents plus keyword router exactly as in AGENTS.md
- `rag/pipeline.py` and `chat_service.py` with the last 6 messages of history
- `POST /chat/ask`, `GET /chat/sessions`, `GET /chat/history`, `GET /repo/files`, `GET /repo/file`
- Sources come only from retrieved chunks, with real line numbers
- Done when: a follow-up like "where is the JWT generated?" after "how does auth work?" is answered using the earlier context

## Phase 5: connect the frontend

- Add Axios with a `services/api.js` using `REACT_APP_API_URL`
- Replace mock calls in `App.jsx`: indexing with status polling, chat, file tree, history
- Add Monaco Editor viewer: clicking a source chip opens the file at the right line range
- Render Gemini's Markdown answers safely
- Add loading indicator, error states, metadata filters and a chat history list
- Done when: the full flow works in the browser against a real repo

## Phase 6: hardening

- pytest for parsers, chunker, router and file-tree path safety
- Test on a web app repo, a LangChain repo and a TensorFlow repo
- Fix retrieval quality problems found in testing
- Write README.md with setup steps for Windows
