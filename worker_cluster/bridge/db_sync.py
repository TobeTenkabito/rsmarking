"""
Worker 专用同步数据库会话
data_service 使用 asyncpg（异步），Worker 进程不运行事件循环，
因此单独维护一个 psycopg2 同步引擎。
连接字符串从同一环境变量派生，仅替换驱动前缀。
"""
import os
import logging
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger("worker.db_sync")

# ── 连接字符串 ────────────────────────────────────────────────────────────────
# 优先读专用变量，回退到把 asyncpg URL 的驱动前缀替换掉
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
    上下文管理器，用法：
        with get_sync_db() as db:
            db.query(...)
    异常时自动回滚，正常时自动提交并关闭。
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
