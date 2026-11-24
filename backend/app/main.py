"""FastAPI entry point. Run from backend/ with: uvicorn app.main:app --reload"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import chat, files, repo
from app.config.settings import ENV_FILE, settings
from app.database.db import check_db_connection, init_db
from app.utils.file_utils import ensure_dir
from app.utils.logger import get_logger

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Runs once at startup: make folders and create database tables."""
    if not ENV_FILE.exists():
        logger.warning("backend/.env not found. Copy .env.example to .env and fill it in.")
    ensure_dir(settings.repos_dir)
    ensure_dir(settings.chroma_dir)
    init_db()  # raises a clear RuntimeError if MySQL is unreachable
    logger.info("RepoLens backend started")
    yield


app = FastAPI(
    title="RepoLens API",
    description="AI repository RAG assistant",
    version="0.1.0",
    lifespan=lifespan,
)

# Allow the React dev server to call this API from the browser
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_ORIGIN],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(repo.router)
app.include_router(files.router)
app.include_router(chat.router)


@app.get("/health", tags=["health"])
def health() -> dict[str, str]:
    """Simple health check that also reports whether MySQL is reachable."""
    return {"status": "ok", "database": "ok" if check_db_connection() else "unreachable"}
