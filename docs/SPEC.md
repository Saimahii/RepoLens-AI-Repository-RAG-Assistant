# RepoLens — AI-Powered Repository RAG Assistant

Build a full-stack AI-powered Repository RAG Assistant called "RepoLens" for developers.

RepoLens should allow users to upload or connect GitHub repositories and ask natural language questions about the codebase.

The platform should analyze repositories intelligently using AST-based parsing, semantic search, RAG pipelines, and multi-agent AI workflows.

The project should remain beginner-friendly, modular, scalable, cleanly structured, and easy to understand.

---

# CORE OBJECTIVE

RepoLens should help developers:

* understand repositories
* explain code
* debug issues
* identify bugs
* understand architecture
* explore dependencies
* retrieve relevant code snippets
* ask contextual questions about repositories

The system should work for:

* normal web repositories
* AI repositories
* TensorFlow projects
* LangChain projects
* backend systems
* frontend applications
* full-stack applications

---

# TECH STACK

Frontend:

* React.js
* Plain CSS
* Axios
* Monaco Editor

Backend:

* Python FastAPI

AI + RAG:

* Gemini API for LLM
* ChromaDB or FAISS for vector database
* sentence-transformers/all-MiniLM-L6-v2 for embeddings

Parsing:

* AST-based parsing
* Python ast module
* Tree-sitter for JavaScript/TypeScript parsing
* Semantic chunk extraction

Database:

* MySQL

ORM:

* SQLAlchemy

---

# IMPORTANT REQUIREMENTS

Keep the project:

* simple
* understandable
* modular
* beginner-friendly
* production-like

DO NOT use:

* Kubernetes
* Microservices
* Docker initially
* Redis
* Celery
* LangGraph
* Complex orchestration systems
* Distributed infrastructure

The codebase must remain easy to understand for student developers.

Focus on:

* clean architecture
* reusable services
* modular folders
* readable code
* comments for beginners
* efficient retrieval quality
* maintainability

---

# PROJECT STRUCTURE

Create this structure:

backend/
│
├── app/
│   ├── api/
│   ├── services/
│   ├── rag/
│   ├── parsers/
│   ├── agents/
│   ├── database/
│   ├── models/
│   ├── schemas/
│   ├── utils/
│   ├── prompts/
│   ├── config/
│   └── main.py
│
├── repos/
│
├── vector_store/
│
├── requirements.txt
│
└── .env

frontend/
│
├── src/
│   ├── components/
│   ├── pages/
│   ├── services/
│   ├── styles/
│   ├── utils/
│   └── App.js

---

# FRONTEND REQUIREMENTS

Build a developer-friendly interface.

Layout:

* Left Sidebar → repository tree + metadata filters
* Center → AI chat interface
* Right Panel → code snippet viewer

Features:

* GitHub repository URL input
* repository indexing status
* chat interface
* syntax-highlighted code snippets
* source references
* metadata filters
* chat history
* loading indicators
* repository file explorer

Use Monaco Editor for code visualization.

---

# BACKEND REQUIREMENTS

Use FastAPI.

Create APIs for:

* repository upload
* repository indexing
* chat
* retrieval
* chat history
* repository metadata

Example endpoints:

POST /repo/upload
POST /repo/index
POST /chat/ask
GET /chat/history
GET /repo/files

---

# REPOSITORY INGESTION FLOW

1. User submits GitHub repository URL

2. Clone repository locally

3. Scan repository files

4. Ignore unnecessary folders:

   * node_modules
   * dist
   * build
   * .git
   * venv
   * **pycache**

5. Read:

   * .py
   * .js
   * .ts
   * .tsx
   * .java
   * .go
   * .md

Store repository metadata in MySQL.

---

# AST-BASED PARSING

Use AST-based parsing for better semantic understanding.

Python:

* use Python ast module

JavaScript/TypeScript:

* use tree-sitter

Extract:

* classes
* functions
* methods
* imports
* routes
* components
* docstrings
* comments

Store metadata:

* file path
* language
* function/class name
* start line
* end line
* imports
* parent module

Avoid naive text chunking.

---

# SMART CHUNKING STRATEGY

Implement semantic chunking.

Chunk by:

* functions
* classes
* methods
* logical code blocks

Each chunk should contain:

* code content
* surrounding context lines
* metadata

Store:

* chunk ID
* file path
* language
* function/class name
* start line
* end line

Avoid random token splitting.

---

# VECTOR DATABASE

Use:

* ChromaDB
  OR
* FAISS

Store:

* embeddings
* metadata
* chunk text

Implement:

* semantic similarity search
* metadata filtering

---

# EMBEDDINGS

Use:
sentence-transformers/all-MiniLM-L6-v2

Generate embeddings for:

* code chunks
* repository summaries
* architecture summaries

---

# GEMINI AI INTEGRATION

Use Gemini API as the LLM.

Gemini should:

* answer repository questions
* explain code
* summarize architecture
* explain bugs
* provide debugging suggestions
* explain dependencies
* explain data flow

Every response must include:

* explanation
* source references
* relevant code snippets
* file paths
* line numbers

---

# HISTORY-AWARE CHAT

Implement conversational memory.

Store in MySQL:

* chat sessions
* user messages
* AI responses

When generating answers:

* include recent chat history
* maintain contextual understanding
* support follow-up questions

Example:
User:
"How authentication works?"

Follow-up:
"Where is JWT generated?"

The model should understand the previous context.

---

# MULTI-AGENT SYSTEM

Create simple prompt-based agents.

Folder:
backend/app/agents/

Implement these agents:

1. Code Explainer Agent
   Purpose:

* explain functions
* explain classes
* explain logic flow
* explain APIs

2. Debugging Agent
   Purpose:

* explain errors
* suggest fixes
* analyze stack traces
* debug logic

3. Bug Finder Agent
   Purpose:

* identify risky patterns
* detect possible bugs
* identify edge cases
* detect anti-patterns

4. Architecture Explainer Agent
   Purpose:

* explain project structure
* explain module relationships
* summarize repository architecture
* explain request/data flow

---

# AGENT ROUTING

Use simple keyword-based routing.

Examples:

If query contains:

* "bug"
* "issue"
* "problem"

→ Bug Finder Agent

If query contains:

* "debug"
* "error"
* "fix"

→ Debugging Agent

If query contains:

* "architecture"
* "flow"
* "structure"

→ Architecture Explainer Agent

Else:
→ Code Explainer Agent

Keep routing simple and understandable.

DO NOT use advanced orchestration frameworks.

---

# RAG PIPELINE

Implement this pipeline:

User Question
→ Query Embedding
→ Vector Search
→ Metadata Filtering
→ Retrieve Relevant Chunks
→ Add Conversation History
→ Send Context to Gemini
→ Generate Final Answer

---

# PROMPT ENGINEERING

Gemini prompts should include:

* system instructions
* repository context
* retrieved chunks
* metadata
* recent conversation history
* selected agent behavior
* user question

The model should answer clearly with references.

---

# CODE SNIPPETS

Every response should contain:

* file path
* line numbers
* code snippet
* surrounding context lines

Use Monaco Editor in frontend for rendering.

---

# MYSQL DATABASE DESIGN

Use MySQL with SQLAlchemy.

Create tables:

* repositories
* indexed_files
* code_chunks
* chat_sessions
* messages

Keep schema simple and understandable.

---

# DEVELOPMENT PHASES

Phase 1:

* FastAPI setup
* MySQL setup
* GitHub repository cloning

Phase 2:

* AST parsing
* semantic chunking
* embeddings generation

Phase 3:

* ChromaDB/FAISS integration
* retrieval pipeline
* Gemini integration

Phase 4:

* React frontend
* Monaco Editor
* chat UI
* repository explorer

Phase 5:

* history-aware chat
* metadata filtering
* multi-agent support

---

# CODING STYLE

Requirements:

* clean architecture
* modular services
* readable functions
* reusable utilities
* beginner-friendly comments
* proper error handling

The project should feel production-ready while remaining easy to understand and maintain.

---

# GENERATE

Generate:

1. Complete folder structure
2. Backend initialization
3. Frontend initialization
4. requirements.txt
5. MySQL configuration
6. AST parsing setup
7. ChromaDB/FAISS setup
8. Gemini integration
9. Multi-agent implementation
10. Step-by-step implementation

Start with backend project initialization first.