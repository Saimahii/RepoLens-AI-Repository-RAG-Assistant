"""/repo file-explorer endpoints: nested file tree and safe single-file viewer."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.schemas.files import FileContentResponse, FileTreeNode
from app.services.file_service import FileServiceError, get_repo_file_tree, read_repo_file

router = APIRouter(prefix="/repo", tags=["files"])


@router.get("/files", response_model=list[FileTreeNode])
def repo_files(
    repo_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> list[FileTreeNode]:
    """Return the nested file tree of indexed files for a repository."""
    try:
        return get_repo_file_tree(db=db, repo_id=repo_id)
    except FileServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("/file", response_model=FileContentResponse)
def repo_file(
    repo_id: int = Query(..., ge=1),
    path: str = Query(..., min_length=1),
    db: Session = Depends(get_db),
) -> FileContentResponse:
    """Safely return the contents of one file inside the repository (blocks path traversal)."""
    try:
        return read_repo_file(db=db, repo_id=repo_id, requested_path=path)
    except FileServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
