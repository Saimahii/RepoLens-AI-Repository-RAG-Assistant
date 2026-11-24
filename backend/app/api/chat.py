"""/chat endpoints: ask questions, list sessions, and fetch chat history."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database.db import get_db
from app.schemas.chat import (
    ChatAskRequest,
    ChatAskResponse,
    ChatMessageResponse,
    ChatSessionResponse,
)
from app.services.chat_service import (
    ChatServiceError,
    ask_question,
    get_session_history,
    list_sessions,
)

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/ask", response_model=ChatAskResponse)
def chat_ask(payload: ChatAskRequest, db: Session = Depends(get_db)) -> ChatAskResponse:
    """Answer a natural-language question about an indexed repository using RAG + Gemini."""
    try:
        return ask_question(
            db=db,
            repo_id=payload.repo_id,
            question=payload.question,
            session_id=payload.session_id,
            filters=payload.filters,
        )
    except ChatServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("/sessions", response_model=list[ChatSessionResponse])
def chat_sessions(
    repo_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> list[ChatSessionResponse]:
    """List saved chat sessions for a repository."""
    try:
        return list_sessions(db=db, repo_id=repo_id)
    except ChatServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error


@router.get("/history", response_model=list[ChatMessageResponse])
def chat_history(
    session_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
) -> list[ChatMessageResponse]:
    """Return all messages in a chat session in chronological order."""
    try:
        return get_session_history(db=db, session_id=session_id)
    except ChatServiceError as error:
        raise HTTPException(status_code=error.status_code, detail=error.message) from error
