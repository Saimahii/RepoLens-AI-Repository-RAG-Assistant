"""/repo endpoints: upload, background indexing, and status polling."""

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.schemas.repo import (
    RepoIndexRequest,
    RepoIndexResponse,
    RepoStatusResponse,
    RepoUploadRequest,
    RepoUploadResponse,
)
from app.services.repo_service import (
    RepoServiceError,
    get_repo_status,
    prepare_repo_for_indexing,
    run_index_pipeline,
    upload_repository,
)

router = APIRouter(prefix="/repo", tags=["repo"])


@router.post("/upload", response_model=RepoUploadResponse)
def upload_repo(payload: RepoUploadRequest, db: Session = Depends(get_db)) -> RepoUploadResponse:
    """Validate a GitHub URL, clone the repo and register it.

    A plain `def` (not async) is used on purpose: git clone blocks, and FastAPI
    runs sync endpoints in a thread pool so other requests keep working.
    """
    try:
        repo = upload_repository(db, payload.github_url)
    except RepoServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
    return RepoUploadResponse(repo_id=repo.id, status=repo.status)


@router.post("/index", response_model=RepoIndexResponse)
def index_repo(
    payload: RepoIndexRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
) -> RepoIndexResponse:
    """Kick off background parsing, chunking, and embedding for an uploaded repo."""
    try:
        repo = prepare_repo_for_indexing(db, payload.repo_id)
    except RepoServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error

    background_tasks.add_task(run_index_pipeline, repo.id)
    return RepoIndexResponse(repo_id=repo.id, status=repo.status)


@router.get("/status/{repo_id}", response_model=RepoStatusResponse)
def repo_status(repo_id: int, db: Session = Depends(get_db)) -> RepoStatusResponse:
    """Return the current indexing status, step, and any error message."""
    try:
        status, step, error = get_repo_status(db, repo_id)
    except RepoServiceError as err:
        raise HTTPException(status_code=err.status_code, detail=err.message) from err
    return RepoStatusResponse(status=status, step=step, error=error)
