"""Pydantic schemas for GET /repo/files and GET /repo/file."""

from __future__ import annotations

from pydantic import BaseModel, Field


class FileTreeNode(BaseModel):
    """One node (folder or file) in the nested repository file tree."""

    name: str
    path: str
    type: str  # "folder" or "file"
    language: str | None = None
    children: list[FileTreeNode] = Field(default_factory=list)


class FileContentResponse(BaseModel):
    """Response of GET /repo/file?repo_id=&path=."""

    path: str
    language: str
    content: str
