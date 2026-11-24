# RepoLens — AI Repository RAG Assistant

RepoLens is a full-stack AI assistant that lets you paste any public GitHub repository URL, index the codebase with AST / Tree-sitter parsing and local embeddings, and ask natural-language questions about the code. Every answer comes with grounded file paths, real line numbers, and a built-in Monaco Editor viewer that jumps straight to the cited lines.

---

## Quick Start: How to Run Backend & Frontend (Windows PowerShell)

> If this is your **very first time** running RepoLens on a new machine, complete **[First-Time Setup](#first-time-setup-windows-powershell)** below first.

You need **two PowerShell terminals** open in the `repolens` project folder.

### Terminal 1 — Start the Backend (FastAPI)

```powershell
cd backend
.\venv\Scripts\uvicorn.exe app.main:app --reload
```

Wait until you see:
```text
Database tables are ready
Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
```

- **Health check:** http://127.0.0.1:8000/health → should show `{"status":"ok","database":"ok"}`
- **API docs (Swagger UI):** http://127.0.0.1:8000/docs

### Terminal 2 — Start the Frontend (React)

Open a **second** PowerShell terminal in the `repolens` root folder and run:

```powershell
cd frontend
npm start
```

Wait until you see:
```text
Compiled successfully!
Local: http://localhost:3000
```

Open **http://localhost:3000** in your browser.

### How to Stop Both Servers

Click inside each PowerShell terminal and press **`Ctrl + C`** (confirm `Y` if asked).

---

## How to Use RepoLens (Step by Step)

### Step 1 — Connect and Index a GitHub Repository

1. Open **http://localhost:3000** — you will see the **Welcome Screen**.
2. Paste any **public** GitHub repository URL into the input box, for example:
   - `https://github.com/pallets/itsdangerous`
   - `https://github.com/fastapi/full-stack-fastapi-template`
3. Click **`Index →`** (or press `Enter`).
4. Watch the **Indexing Bar** at the top of the screen move through all 4 steps:
   - **Cloning** → shallow-clones the repo into `backend/repos/`
   - **Parsing AST** → parses `.py` (AST), `.js/.ts/.tsx` (Tree-sitter), and `.java/.go/.md` (fallback windows) and saves chunks to MySQL
   - **Embedding** → generates local MiniLM embeddings and saves vectors to ChromaDB
   - **Ready** → shows `✓ Repository indexed and ready`
   - *(If the repo was already indexed earlier, it loads immediately. Click **Re-index** on the top bar anytime you want a fresh parse & embed.)*

### Step 2 — Ask Questions About the Code

1. Once the bar says **`✓ Repository indexed and ready`**, type any question in the bottom input box and press **`Enter`** (or click the **↑ Send** button).
2. You can also click any chip under **Suggested tasks** or **Suggested questions** in the right panel.
3. RepoLens automatically picks the right AI agent based on keywords in your question and displays its badge above the answer:
   - **`bug` / `issue` / `problem`** → **Bug Finder** (spots risky patterns, edge cases, potential bugs)
   - **`debug` / `error` / `fix`** → **Debugger** (diagnoses errors and suggests fixes)
   - **`architecture` / `flow` / `structure`** → **Architecture Explainer** (explains structure, modules, and data flow)
   - **Everything else** → **Code Explainer** (explains functions, classes, and APIs)

### Step 3 — Ask Follow-Up Questions

RepoLens remembers the **last 6 messages** in your active chat session.
- Example Turn 1: *"How does timestamp signing work in this repository?"*
- Example Turn 2: *"Where is it validated and what error is raised if it expired?"*

Because it keeps session context, you do not need to repeat file or class names in follow-ups.

### Step 4 — Inspect Sources in the Monaco Code Viewer

1. Above each AI answer, you will see clickable **SOURCES** chips like `src/itsdangerous/timed.py:22-167`.
2. **Click any source chip** to open that file in the **Monaco Editor** popup — it automatically scrolls to and highlights the exact cited line range in purple.
3. Press **`Esc`** or click **`✕`** to close the viewer (or click **Copy file** to copy the full file).
4. Use the **Citation** toggle in the bottom input bar to show or hide source chips.
5. Below any AI answer, click **Copy** to copy the Markdown answer or **Rewrite** to regenerate it.

### Step 5 — Browse Files with the File Explorer

1. In the **right panel**, scroll to **File Explorer**.
2. Click any folder (`▸ src`, `▸ app`, etc.) to expand or collapse it.
3. Click any file to open it directly in the **Monaco Editor** viewer.

### Step 6 — Narrow Search with Retrieval Filters

In the **Retrieval Filters** card (top of the right panel):
- **Language:** limit retrieval to one language (`Python`, `JavaScript`, `TypeScript`, `TSX`, `Java`, `Go`, `Markdown`, or `All languages`).
- **Path prefix:** restrict retrieval to a subfolder (for example `src/itsdangerous/` or `backend/app/api/`).
- Click **Clear** to reset both filters.

### Step 7 — Manage Sessions & Switch Repositories

- **Chat History (right panel):** click any saved session to reload its full conversation and sources from MySQL.
- **`+ New` / `New Thread` (top navbar):** start a fresh chat session on the currently connected repository.
- **`Switch Repo` (top navbar) or the Home icon (left sidebar):** return to the Welcome Screen to connect a different GitHub repository.

---

## First-Time Setup (Windows PowerShell)

### Prerequisites

Install these once on your Windows machine:
1. **Python 3.12 or 3.13** — [python.org](https://www.python.org/downloads/)
2. **Node.js 18+ (includes npm)** — [nodejs.org](https://nodejs.org/)
3. **Git for Windows** — [git-scm.com](https://git-scm.com/download/win) (must be on `PATH`)
4. **MySQL Server 8.0** — [dev.mysql.com](https://dev.mysql.com/downloads/installer/)
5. **Google Gemini API Key** — [Google AI Studio](https://aistudio.google.com/apikey)

### 1. Start MySQL and Create the Database

In PowerShell (**Run as Administrator** if MySQL is stopped):

```powershell
Get-Service MySQL*
# If Status is Stopped:
Start-Service MySQL80
```

Log into MySQL as `root`:

```powershell
& "C:\Program Files\MySQL\MySQL Server 8.0\bin\mysql.exe" -u root -p
```

Run these SQL commands (replace `YourPassword123` with your own password):

```sql
CREATE DATABASE IF NOT EXISTS repolens CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'repolens_user'@'localhost' IDENTIFIED BY 'YourPassword123';
GRANT ALL PRIVILEGES ON repolens.* TO 'repolens_user'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

*(Tables are created automatically when the backend starts.)*

### 2. Install Backend Dependencies & Configure `backend\.env`

From the `repolens` root folder:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\pip.exe install -r requirements.txt
Copy-Item .env.example .env
```

Open `backend\.env` and fill in your values:

```env
DATABASE_URL=mysql+pymysql://repolens_user:YourPassword123@localhost:3306/repolens
GEMINI_API_KEY=your_gemini_api_key_here
GEMINI_MODEL=gemini-3.5-flash-lite
CHROMA_PATH=vector_store
REPOS_PATH=repos
CLONE_TIMEOUT_SECONDS=120
```

> **Special characters in MySQL passwords:** If your password contains `@`, `:`, `/`, `#`, or `%`, URL-encode them in `DATABASE_URL` (for example `@` becomes `%40`).

### 3. Install Frontend Dependencies & Configure `frontend\.env`

From the `repolens` root folder:

```powershell
cd frontend
npm install
Copy-Item .env.example .env
```

Confirm `frontend\.env` contains:

```env
REACT_APP_API_URL=http://127.0.0.1:8000
```

Now jump back up to **[Quick Start: How to Run Backend & Frontend](#quick-start-how-to-run-backend--frontend-windows-powershell)**!

---

## Tech Stack & Folder Structure

- **Frontend:** React.js (Create React App), plain CSS, Axios, Monaco Editor (`@monaco-editor/react`), `react-markdown` + `remark-gfm`
- **Backend:** Python FastAPI, SQLAlchemy 2.x, MySQL 8 (`PyMySQL`), FastAPI `BackgroundTasks`
- **AI & Search:** Google Gen AI SDK (`google-genai`), `sentence-transformers/all-MiniLM-L6-v2`, ChromaDB (`backend/vector_store/`)
- **Parsing:** Python `ast` (`.py`), Tree-sitter (`.js`, `.ts`, `.tsx`), line-window fallback (`.java`, `.go`, `.md`)

```text
repolens/
├── backend/
│   ├── app/
│   │   ├── api/          # repo.py, chat.py, files.py
│   │   ├── services/     # repo_service, embedding_service, vector_store, gemini_service, chat_service, file_service
│   │   ├── rag/          # retriever.py (filters + hybrid re-ranking), pipeline.py
│   │   ├── parsers/      # python_parser.py, js_parser.py, fallback_parser.py, chunker.py
│   │   ├── agents/       # base_agent, explainer, debugger, bug_finder, architect, router
│   │   ├── prompts/      # system + per-agent prompt templates
│   │   ├── database/     # db.py
│   │   ├── models/       # repositories, indexed_files, code_chunks, chat_sessions, messages
│   │   ├── schemas/      # Pydantic request/response schemas
│   │   ├── utils/        # file_utils, helpers, logger
│   │   ├── config/       # settings.py
│   │   └── main.py       # FastAPI entry point + CORS + /health
│   ├── tests/            # 82 pytest unit tests
│   ├── repos/            # cloned repos (git-ignored)
│   ├── vector_store/     # ChromaDB data (git-ignored)
│   ├── requirements.txt
│   └── .env.example
└── frontend/
    ├── src/
    │   ├── components/   # WelcomeScreen, Indexingbar, ChatThread, AIMessage, CodeBlock, CodeViewerModal, RightPannel, ...
    │   ├── services/     # api.js (Axios client)
    │   ├── styles/       # Plain CSS files
    │   ├── utils/        # Inline SVG icons
    │   └── App.jsx
    ├── package.json
    └── .env.example
```

---

## Running Tests & Production Build

**Backend test suite (`pytest`):**
```powershell
cd backend
.\venv\Scripts\pytest.exe -v
```

**Frontend production build:**
```powershell
cd frontend
npm run build
```

---

## API Reference

| Method & Endpoint | Description |
|---|---|
| `GET /health` | Checks server and MySQL connectivity |
| `POST /repo/upload` | Validates GitHub URL, shallow-clones repo, saves metadata in MySQL |
| `POST /repo/index` | Starts background AST/Tree-sitter parsing and MiniLM embedding |
| `GET /repo/status/{repo_id}` | Returns `{status, step, error}` for live progress polling |
| `GET /repo/files?repo_id=` | Returns nested repository file tree |
| `GET /repo/file?repo_id=&path=` | Safely reads a file inside the repo (blocks path traversal) |
| `POST /chat/ask` | Runs RAG retrieval, agent routing, Gemini generation, and saves messages |
| `GET /chat/sessions?repo_id=` | Lists saved chat sessions for a repository |
| `GET /chat/history?session_id=` | Returns stored messages and sources in chronological order |

---

## Troubleshooting (Windows)

- **PowerShell blocks `Activate.ps1`:** Skip activation and call `.\venv\Scripts\uvicorn.exe` and `.\venv\Scripts\pytest.exe` directly (as shown above).
- **MySQL `Access denied` or wrong host error:** Confirm MySQL is running (`Get-Service MySQL*`), verify username/password in `backend\.env`, and encode `@` in your password as `%40`.
- **Frontend shows "Could not reach the backend":** Make sure Terminal 1 (`uvicorn`) is running on port `8000` and `frontend\.env` has `REACT_APP_API_URL=http://127.0.0.1:8000`.
- **Gemini `503 UNAVAILABLE` or `404` model error:** Update `GEMINI_MODEL` in `backend\.env` to an available Flash model for your API key and restart `uvicorn`. List models available to your key with:
  ```powershell
  cd backend
  .\venv\Scripts\python.exe -c "from google import genai; from app.config.settings import settings; print([m.name for m in genai.Client(api_key=settings.GEMINI_API_KEY).models.list() if 'flash' in (m.name or '')])"
  ```
- **First indexing takes a little longer:** The very first run downloads `sentence-transformers/all-MiniLM-L6-v2` (~90 MB) into your local cache; after that, it loads from cache in under a second.
