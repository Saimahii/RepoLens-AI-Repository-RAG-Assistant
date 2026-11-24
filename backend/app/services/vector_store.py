"""Persistent ChromaDB wrapper stored under backend/vector_store/."""

from threading import Lock
from typing import Any

from app.config.settings import settings
from app.utils.file_utils import ensure_dir
from app.utils.logger import get_logger

logger = get_logger(__name__)

COLLECTION_NAME: str = "repolens_chunks"
UPSERT_BATCH_SIZE: int = 200

_chroma_lock = Lock()
_collection_instance: Any | None = None


class VectorStoreError(Exception):
    """Raised when ChromaDB initialization, upsert, delete, or query fails."""


def get_collection() -> Any:
    """Return the shared persistent ChromaDB collection (created lazily once)."""
    global _collection_instance
    if _collection_instance is not None:
        return _collection_instance

    with _chroma_lock:
        if _collection_instance is not None:
            return _collection_instance
        try:
            import chromadb

            chroma_dir = ensure_dir(settings.chroma_dir)
            client = chromadb.PersistentClient(path=str(chroma_dir))
            _collection_instance = client.get_or_create_collection(
                name=COLLECTION_NAME,
                metadata={"hnsw:space": "cosine"},
            )
            logger.info("ChromaDB collection '%s' ready at %s", COLLECTION_NAME, chroma_dir)
            return _collection_instance
        except Exception as error:
            logger.error("Failed to initialize ChromaDB at %s: %s", settings.chroma_dir, error)
            raise VectorStoreError(f"Could not initialize ChromaDB: {error}") from error


def delete_repo_vectors(repo_id: int) -> None:
    """Delete all stored vectors belonging to one repository (used before re-indexing)."""
    collection = get_collection()
    try:
        collection.delete(where={"repo_id": int(repo_id)})
        logger.info("Deleted existing ChromaDB vectors for repo_id=%s", repo_id)
    except Exception as error:
        logger.error("Failed to delete vectors for repo_id=%s: %s", repo_id, error)
        raise VectorStoreError(f"Failed to clear old vectors for repo_id={repo_id}: {error}") from error


def upsert_vectors(
    ids: list[str],
    embeddings: list[list[float]],
    documents: list[str],
    metadatas: list[dict[str, str | int | float | bool]],
) -> None:
    """Upsert vectors into ChromaDB in safe batches."""
    if not ids:
        return
    if not (len(ids) == len(embeddings) == len(documents) == len(metadatas)):
        raise VectorStoreError("Mismatched vector payload lengths during ChromaDB upsert.")

    collection = get_collection()
    try:
        for start in range(0, len(ids), UPSERT_BATCH_SIZE):
            end = start + UPSERT_BATCH_SIZE
            collection.upsert(
                ids=ids[start:end],
                embeddings=embeddings[start:end],
                documents=documents[start:end],
                metadatas=metadatas[start:end],
            )
        logger.info("Upserted %d vectors into ChromaDB collection '%s'", len(ids), COLLECTION_NAME)
    except Exception as error:
        logger.error("ChromaDB upsert failed: %s", error)
        raise VectorStoreError(f"Failed to store vectors in ChromaDB: {error}") from error


def build_where_filter(
    repo_id: int,
    language: str | None = None,
    chunk_kind: str | None = None,
) -> dict[str, Any]:
    """Build a valid ChromaDB `where` filter dict."""
    conditions: list[dict[str, Any]] = [{"repo_id": int(repo_id)}]
    if language:
        conditions.append({"language": language.lower().strip()})
    if chunk_kind:
        conditions.append({"chunk_kind": chunk_kind})

    if len(conditions) == 1:
        return conditions[0]
    return {"$and": conditions}


def query_vectors(
    query_embedding: list[float],
    repo_id: int,
    n_results: int = 8,
    language: str | None = None,
    chunk_kind: str | None = None,
) -> dict[str, list[Any]]:
    """Run cosine similarity search against ChromaDB with metadata filters."""
    collection = get_collection()
    try:
        total_items = collection.count()
        if total_items == 0 or n_results <= 0:
            return {"ids": [], "documents": [], "metadatas": [], "distances": []}

        where = build_where_filter(repo_id=repo_id, language=language, chunk_kind=chunk_kind)
        raw = collection.query(
            query_embeddings=[query_embedding],
            n_results=min(n_results, total_items),
            where=where,
            include=["documents", "metadatas", "distances"],
        )
        return {
            "ids": (raw.get("ids") or [[]])[0],
            "documents": (raw.get("documents") or [[]])[0],
            "metadatas": (raw.get("metadatas") or [[]])[0],
            "distances": (raw.get("distances") or [[]])[0],
        }
    except Exception as error:
        logger.error("ChromaDB query failed for repo_id=%s: %s", repo_id, error)
        raise VectorStoreError(f"Vector search failed: {error}") from error


def count_repo_vectors(repo_id: int) -> int:
    """Count how many vectors are currently stored for a given repository."""
    collection = get_collection()
    try:
        result = collection.get(where={"repo_id": int(repo_id)}, include=[])
        return len(result.get("ids") or [])
    except Exception as error:
        logger.error("ChromaDB count failed for repo_id=%s: %s", repo_id, error)
        raise VectorStoreError(f"Failed to count vectors for repo_id={repo_id}: {error}") from error
