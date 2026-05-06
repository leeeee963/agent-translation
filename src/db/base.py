"""Engine and session lifecycle.

Reads DATABASE_URL at startup; falls back to SQLite at data/app.db.
"""

from __future__ import annotations

import logging
import os
from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from src.utils.paths import get_data_dir

logger = logging.getLogger(__name__)


def _resolve_database_url() -> str:
    raw = os.getenv("DATABASE_URL", "").strip()
    if raw:
        # Heroku-style "postgres://..." → SQLAlchemy needs explicit driver
        if raw.startswith("postgres://"):
            raw = raw.replace("postgres://", "postgresql+psycopg2://", 1)
        elif raw.startswith("postgresql://") and "+" not in raw.split("://", 1)[0]:
            raw = raw.replace("postgresql://", "postgresql+psycopg2://", 1)
        return raw

    db_path = get_data_dir() / "data" / "app.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path}"


_engine: Engine | None = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is not None:
        return _engine

    url = _resolve_database_url()
    is_sqlite = url.startswith("sqlite")

    connect_args: dict = {}
    if is_sqlite:
        connect_args["check_same_thread"] = False

    _engine = create_engine(
        url,
        connect_args=connect_args,
        pool_pre_ping=True,
        future=True,
    )

    if is_sqlite:
        @event.listens_for(_engine, "connect")
        def _set_sqlite_pragma(dbapi_conn, _record) -> None:  # noqa: ANN001
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

    logger.info("DB engine initialized: %s", "sqlite" if is_sqlite else "postgres")
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    global _SessionLocal
    if _SessionLocal is None:
        _SessionLocal = sessionmaker(
            bind=get_engine(),
            expire_on_commit=False,
            class_=Session,
        )
    return _SessionLocal


@contextmanager
def session_scope() -> Iterator[Session]:
    """Transactional scope: commits on success, rolls back on exception."""
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def init_db() -> None:
    """Create all tables. Idempotent."""
    from src.db.models import Base
    Base.metadata.create_all(bind=get_engine())


def dispose_engine() -> None:
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None
