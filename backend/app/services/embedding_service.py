"""Local embedding service using sentence-transformers/all-MiniLM-L6-v2.

The model is loaded lazily once and reused across indexing and queries.
"""

from threading import Lock
from typing import Sequence

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)

_model_lock = Lock()
_model_instance: object | None = None


class EmbeddingServiceError(Exception):
    """Raised when loading the embedding model or encoding text fails."""


def get_embedding_model():
    """Load and cache the SentenceTransformer model once (thread-safe)."""
    global _model_instance
    if _model_instance is not None:
        return _model_instance

    with _model_lock:
        if _model_instance is not None:
            return _model_instance
        try:
            # Deferred import keeps startup and non-embedding unit tests fast
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model %s...", settings.EMBEDDING_MODEL)
            try:
                # Prefer local cache first so cold starts skip slow HuggingFace HEAD checks
                _model_instance = SentenceTransformer(
                    settings.EMBEDDING_MODEL,
                    local_files_only=True,
                )
            except Exception:
                logger.info("Model not in local cache yet; downloading %s...", settings.EMBEDDING_MODEL)
                _model_instance = SentenceTransformer(settings.EMBEDDING_MODEL)
            logger.info("Embedding model loaded successfully.")
            return _model_instance
        except Exception as error:
            logger.error("Failed to load embedding model %s: %s", settings.EMBEDDING_MODEL, error)
            raise EmbeddingServiceError(
                f"Could not load embedding model '{settings.EMBEDDING_MODEL}': {error}"
            ) from error


def build_chunk_embedding_text(
    file_path: str,
    language: str,
    symbol_type: str,
    symbol_name: str | None,
    parent: str | None,
    content: str,
) -> str:
    """Format a chunk with lightweight metadata so semantic search matches paths and symbol names."""
    header_parts = [f"File: {file_path}", f"Language: {language}", f"Type: {symbol_type}"]
    if symbol_name:
        header_parts.append(f"Symbol: {symbol_name}")
    if parent:
        header_parts.append(f"Parent: {parent}")
    header = " | ".join(header_parts)
    return f"{header}\n\n{content}"


def embed_texts(texts: Sequence[str], batch_size: int = 32) -> list[list[float]]:
    """Batch-encode a sequence of texts into normalized float vectors."""
    if not texts:
        return []

    model = get_embedding_model()
    try:
        vectors = model.encode(
            list(texts),
            batch_size=batch_size,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
        return [vector.tolist() for vector in vectors]
    except Exception as error:
        logger.error("Batch embedding failed for %d texts: %s", len(texts), error)
        raise EmbeddingServiceError(f"Failed to generate embeddings: {error}") from error


def embed_query(query: str) -> list[float]:
    """Encode a single natural-language search query into a normalized vector."""
    cleaned = query.strip()
    if not cleaned:
        raise EmbeddingServiceError("Query text cannot be empty.")
    return embed_texts([cleaned], batch_size=1)[0]
