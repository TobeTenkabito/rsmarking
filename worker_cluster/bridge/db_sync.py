"""
Worker dedicated synchronous database session
data_service uses asyncpg(async),Worker process does not run an event loop,
therefore maintain a separate psycopg2 synchronous engine.
connection stringderived from the same environment variable,only replacing the driver prefix.
"""
import os
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger("worker.db_sync")

# ── connection string ────────────────────────────────────────────────────────────────
# read dedicated variable first,fallback to replacing asyncpg URL driver prefix
def _to_sync_database_url(url: str) -> str:
    if url.startswith("postgresql+asyncpg://"):
        return url.replace("postgresql+asyncpg://", "postgresql+psycopg2://", 1)
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg2://", 1)
    return url


_async_url: str = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://rs_admin:rs_password@localhost:5432/rsmarking",
)
SYNC_DATABASE_URL: str = os.getenv(
    "SYNC_DATABASE_URL",
    _to_sync_database_url(_async_url),
)

_engine: Engine | None = None
_SessionFactory: sessionmaker[Session] | None = None


def _get_session_factory() -> sessionmaker[Session]:
    global _engine, _SessionFactory
    if _SessionFactory is None:
        _engine = create_engine(
            SYNC_DATABASE_URL,
            pool_size=5,
            max_overflow=10,
            pool_pre_ping=True,
            echo=False,
        )
        _SessionFactory = sessionmaker(bind=_engine, autocommit=False, autoflush=False)
    return _SessionFactory


@contextmanager
def get_sync_db() -> Session:
    """
    context manager,usage:
        with get_sync_db() as db:
            db.query(...)
    rollback automatically on exceptions,commit and close automatically on success.
    """
    session: Session = _get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
