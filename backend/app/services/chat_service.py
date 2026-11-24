"""Chat service: session lifecycle, 6-message conversational memory, and MySQL persistence."""

import json

from sqlalchemy import desc, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.models.chat_session import ChatSession
from app.models.message import Message
from app.models.repository import Repository
from app.rag.pipeline import run_rag_pipeline
from app.schemas.chat import (
    ChatAskResponse,
    ChatFilters,
    ChatMessageResponse,
    ChatSessionResponse,
    SourceItem,
)
from app.services.embedding_service import EmbeddingServiceError
from app.services.gemini_service import GeminiServiceError
from app.services.vector_store import VectorStoreError
from app.utils.logger import get_logger

logger = get_logger(__name__)

RECENT_HISTORY_LIMIT: int = 6
MAX_SESSION_TITLE_CHARS: int = 80


class ChatServiceError(Exception):
    """Base error for chat endpoints carrying an HTTP status code."""

    status_code: int = 500

    def __init__(self, message: str, status_code: int = 500) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


class ChatNotFoundError(ChatServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=404)


class ChatValidationError(ChatServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=400)


class ChatDatabaseError(ChatServiceError):
    def __init__(self, message: str) -> None:
        super().__init__(message, status_code=500)


def _make_session_title(question: str) -> str:
    """Create a concise chat session title from the first question."""
    cleaned = " ".join(question.strip().split())
    if len(cleaned) <= MAX_SESSION_TITLE_CHARS:
        return cleaned or "New chat"
    return cleaned[: MAX_SESSION_TITLE_CHARS - 3] + "..."


def _parse_sources_json(raw: str | None) -> list[SourceItem]:
    """Safely deserialize sources_json stored in MySQL."""
    if not raw:
        return []
    try:
        items = json.loads(raw)
        if not isinstance(items, list):
            return []
        return [SourceItem.model_validate(item) for item in items]
    except (ValueError, TypeError) as error:
        logger.warning("Could not parse stored sources_json: %s", error)
        return []


def _get_recent_history(db: Session, session_id: int, limit: int = RECENT_HISTORY_LIMIT) -> list[dict[str, str]]:
    """Fetch the last `limit` messages of a session in chronological order."""
    try:
        rows = list(
            db.scalars(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(desc(Message.id))
                .limit(limit)
            ).all()
        )
    except SQLAlchemyError as error:
        logger.error("Could not load chat history for session_id=%s: %s", session_id, error)
        raise ChatDatabaseError("Failed to read chat history from MySQL.") from error

    rows.reverse()
    return [{"role": row.role, "content": row.content} for row in rows]


def ask_question(
    db: Session,
    repo_id: int,
    question: str,
    session_id: int | None = None,
    filters: ChatFilters | None = None,
) -> ChatAskResponse:
    """Handle POST /chat/ask: load context & history, run RAG + Gemini, persist to MySQL."""
    cleaned_question = question.strip()
    if not cleaned_question:
        raise ChatValidationError("Question cannot be empty.")

    try:
        repo = db.scalars(select(Repository).where(Repository.id == repo_id)).first()
    except SQLAlchemyError as error:
        logger.error("Failed to fetch repository id=%s: %s", repo_id, error)
        raise ChatDatabaseError("Could not read repository from MySQL.") from error

    if repo is None:
        raise ChatNotFoundError(f"Repository id={repo_id} not found.")
    if repo.status != "done":
        raise ChatValidationError(
            f"Repository '{repo.name}' is not indexed yet (current status: {repo.status}). "
            "Run POST /repo/index and wait until status is 'done'."
        )

    # Resolve or create the chat session
    session: ChatSession | None = None
    history: list[dict[str, str]] = []
    if session_id is not None:
        try:
            session = db.scalars(select(ChatSession).where(ChatSession.id == session_id)).first()
        except SQLAlchemyError as error:
            logger.error("Failed to fetch session id=%s: %s", session_id, error)
            raise ChatDatabaseError("Could not read chat session from MySQL.") from error
        if session is None:
            raise ChatNotFoundError(f"Chat session id={session_id} not found.")
        if session.repository_id != repo.id:
            raise ChatValidationError(
                f"Chat session id={session_id} does not belong to repository id={repo.id}."
            )
        history = _get_recent_history(db, session.id, limit=RECENT_HISTORY_LIMIT)

    # Run RAG pipeline before saving so a failed Gemini/vector call doesn't leave orphan turns
    try:
        rag_result = run_rag_pipeline(
            db=db,
            repo=repo,
            question=cleaned_question,
            history=history,
            filters=filters,
        )
    except GeminiServiceError as error:
        raise ChatServiceError(error.message, status_code=error.status_code) from error
    except (EmbeddingServiceError, VectorStoreError) as error:
        raise ChatServiceError(str(error), status_code=503) from error

    # Persist session (if new) + user message + assistant response in one transaction
    try:
        if session is None:
            session = ChatSession(repository_id=repo.id, title=_make_session_title(cleaned_question))
            db.add(session)
            db.flush()

        user_msg = Message(
            session_id=session.id,
            role="user",
            content=cleaned_question,
            agent=None,
            sources_json=None,
        )
        sources_payload = json.dumps([s.model_dump() for s in rag_result.sources])
        assistant_msg = Message(
            session_id=session.id,
            role="assistant",
            content=rag_result.answer,
            agent=rag_result.agent,
            sources_json=sources_payload,
        )
        db.add(user_msg)
        db.add(assistant_msg)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        logger.error("Failed to save chat messages for repo_id=%s: %s", repo.id, error)
        raise ChatDatabaseError("Could not save chat messages to MySQL.") from error

    return ChatAskResponse(
        session_id=session.id,
        agent=rag_result.agent,
        answer=rag_result.answer,
        sources=rag_result.sources,
    )


def list_sessions(db: Session, repo_id: int) -> list[ChatSessionResponse]:
    """Return all chat sessions for a repository, newest first."""
    try:
        repo = db.scalars(select(Repository).where(Repository.id == repo_id)).first()
    except SQLAlchemyError as error:
        logger.error("Failed to check repository id=%s: %s", repo_id, error)
        raise ChatDatabaseError("Could not read repository from MySQL.") from error
    if repo is None:
        raise ChatNotFoundError(f"Repository id={repo_id} not found.")

    try:
        sessions = db.scalars(
            select(ChatSession)
            .where(ChatSession.repository_id == repo_id)
            .order_by(desc(ChatSession.id))
        ).all()
    except SQLAlchemyError as error:
        logger.error("Failed to list sessions for repo_id=%s: %s", repo_id, error)
        raise ChatDatabaseError("Could not load chat sessions from MySQL.") from error

    return [
        ChatSessionResponse(
            id=s.id,
            repository_id=s.repository_id,
            title=s.title,
            created_at=s.created_at,
        )
        for s in sessions
    ]


def get_session_history(db: Session, session_id: int) -> list[ChatMessageResponse]:
    """Return all stored messages for a chat session in chronological order."""
    try:
        session = db.scalars(select(ChatSession).where(ChatSession.id == session_id)).first()
    except SQLAlchemyError as error:
        logger.error("Failed to fetch session id=%s: %s", session_id, error)
        raise ChatDatabaseError("Could not read chat session from MySQL.") from error
    if session is None:
        raise ChatNotFoundError(f"Chat session id={session_id} not found.")

    try:
        messages = db.scalars(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.id.asc())
        ).all()
    except SQLAlchemyError as error:
        logger.error("Failed to load messages for session_id=%s: %s", session_id, error)
        raise ChatDatabaseError("Could not load chat history from MySQL.") from error

    return [
        ChatMessageResponse(
            id=m.id,
            session_id=m.session_id,
            role=m.role,
            content=m.content,
            agent=m.agent,
            sources=_parse_sources_json(m.sources_json),
            created_at=m.created_at,
        )
        for m in messages
    ]
