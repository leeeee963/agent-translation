"""Database layer — ORM models, engine, and session factory.

Backed by SQLAlchemy 2.x. Switches between SQLite (local dev) and Postgres
(production) via the DATABASE_URL environment variable.
"""

from src.db.base import (
    dispose_engine,
    get_engine,
    get_session_factory,
    init_db,
    session_scope,
)
from src.db.models import Base, Domain, Job, LibraryTerm, User

__all__ = [
    "Base",
    "Domain",
    "Job",
    "LibraryTerm",
    "User",
    "dispose_engine",
    "get_engine",
    "get_session_factory",
    "init_db",
    "session_scope",
]
