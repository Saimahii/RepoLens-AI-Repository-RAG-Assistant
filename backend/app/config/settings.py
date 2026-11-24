"""Application settings, loaded from backend/.env using pydantic-settings."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ folder: settings.py -> config -> app -> backend
BACKEND_DIR: Path = Path(__file__).resolve().parents[2]
ENV_FILE: Path = BACKEND_DIR / ".env"


class Settings(BaseSettings):
    """All configurable values. Each field can be overridden in .env."""

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",  # ignore unknown keys in .env instead of crashing
    )

    DATABASE_URL: str = "mysql+pymysql://repolens_user:YOUR_PASSWORD@localhost:3306/repolens"
    GEMINI_API_KEY: str = ""
    GEMINI_MODEL: str = ""
    GEMINI_TIMEOUT_SECONDS: int = 60
    GEMINI_MAX_RETRIES: int = 3
    EMBEDDING_MODEL: str = "sentence-transformers/all-MiniLM-L6-v2"
    CHROMA_PATH: str = "vector_store"
    REPOS_PATH: str = "repos"
    CLONE_TIMEOUT_SECONDS: int = 120
    FRONTEND_ORIGIN: str = "http://localhost:3000"

    def _resolve(self, value: str) -> Path:
        """Turn a relative path from .env into an absolute path inside backend/."""
        path = Path(value)
        return path if path.is_absolute() else (BACKEND_DIR / path).resolve()

    @property
    def repos_dir(self) -> Path:
        """Absolute folder where repositories are cloned."""
        return self._resolve(self.REPOS_PATH)

    @property
    def chroma_dir(self) -> Path:
        """Absolute folder for ChromaDB data."""
        return self._resolve(self.CHROMA_PATH)


@lru_cache
def get_settings() -> Settings:
    """Return one shared Settings instance (read .env only once)."""
    return Settings()


settings: Settings = get_settings()
