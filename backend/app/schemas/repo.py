"""Schemas for the /repo endpoints (shapes match the frontend API contract)."""

from pydantic import BaseModel, Field


class RepoUploadRequest(BaseModel):
    """Body of POST /repo/upload."""

    github_url: str = Field(
        ...,
        min_length=1,
        max_length=500,
        examples=["https://github.com/octocat/Hello-World"],
    )


class RepoUploadResponse(BaseModel):
    """Response of POST /repo/upload."""

    repo_id: int
    status: str


class RepoIndexRequest(BaseModel):
    """Body of POST /repo/index."""

    repo_id: int = Field(..., ge=1)


class RepoIndexResponse(BaseModel):
    """Response of POST /repo/index."""

    repo_id: int
    status: str


class RepoStatusResponse(BaseModel):
    """Response of GET /repo/status/{repo_id}."""

    status: str
    step: str
    error: str | None = None
