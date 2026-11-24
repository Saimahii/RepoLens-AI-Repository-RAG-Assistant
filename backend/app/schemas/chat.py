"""Pydantic schemas for /chat endpoints (matching the frontend API contract)."""

from datetime import datetime

from pydantic import BaseModel, Field


class ChatFilters(BaseModel):
    """Optional retrieval filters passed on POST /chat/ask."""

    language: str | None = None
    path_prefix: str | None = None


class ChatAskRequest(BaseModel):
    """Body of POST /chat/ask."""

    repo_id: int = Field(..., ge=1)
    session_id: int | None = Field(default=None, ge=1)
    question: str = Field(..., min_length=1, max_length=4000)
    filters: ChatFilters | None = None


class SourceItem(BaseModel):
    """One grounded source reference returned with an AI answer."""

    file_path: str
    start_line: int
    end_line: int
    language: str
    symbol_name: str | None = None
    snippet: str


class ChatAskResponse(BaseModel):
    """Response of POST /chat/ask."""

    session_id: int
    agent: str
    answer: str
    sources: list[SourceItem]


class ChatSessionResponse(BaseModel):
    """One item returned by GET /chat/sessions?repo_id=."""

    id: int
    repository_id: int
    title: str
    created_at: datetime


class ChatMessageResponse(BaseModel):
    """One message returned by GET /chat/history?session_id=."""

    id: int
    session_id: int
    role: str
    content: str
    agent: str | None = None
    sources: list[SourceItem] = Field(default_factory=list)
    created_at: datetime
