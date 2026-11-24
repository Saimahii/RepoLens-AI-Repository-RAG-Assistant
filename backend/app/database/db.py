"""SQLAlchemy setup: engine, SessionLocal, Base, get_db and init_db."""

from typing import Generator

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError, SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config.settings import settings
from app.utils.logger import get_logger

logger = get_logger(__name__)


class Base(DeclarativeBase):
    """Parent class for all SQLAlchemy models."""


try:
    # pool_pre_ping checks a connection is alive before using it, and
    # pool_recycle avoids MySQL's "server has gone away" after long idle periods.
    engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, pool_recycle=3600)
except ArgumentError as error:
    raise RuntimeError(
        f"DATABASE_URL in backend/.env is not a valid SQLAlchemy URL: {error}"
    ) from error

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: open a session per request and always close it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def safe_db_url() -> str:
    """Return DATABASE_URL with the password hidden, for logs."""
    return make_url(settings.DATABASE_URL).render_as_string(hide_password=True)


def check_db_connection() -> bool:
    """Run SELECT 1 to check MySQL is reachable. Returns True/False, never raises."""
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return True
    except SQLAlchemyError as error:
        logger.error("Database check failed: %s", error)
        return False


def init_db() -> None:
    """Create all tables that do not exist yet.

    Importing app.models registers every model on Base.metadata, so
    create_all knows which tables to build.
    """
    import app.models  # noqa: F401  (import needed for its side effect)

    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables are ready (%s)", safe_db_url())
    except SQLAlchemyError as error:
        raise RuntimeError(
            "Could not connect to MySQL or create tables. Check that the MySQL service "
            f"is running and DATABASE_URL in backend/.env is correct ({safe_db_url()}). "
            f"Details: {error}"
        ) from error
