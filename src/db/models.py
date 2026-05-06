"""SQLAlchemy ORM models — schema is portable across SQLite and Postgres."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


# ── User (schema reserved; no API exposure yet) ──────────────────────
class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(32), default="user")  # "admin" | "user"
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


# ── Translation jobs ─────────────────────────────────────────────────
class Job(Base):
    __tablename__ = "jobs"

    job_id: Mapped[str] = mapped_column(String(32), primary_key=True)
    owner_id: Mapped[int] = mapped_column(Integer, default=0, index=True)  # 0 = shared
    filename: Mapped[str] = mapped_column(String(512), default="")
    source_language: Mapped[str] = mapped_column(String(32), default="")
    target_languages: Mapped[list[str]] = mapped_column(JSON, default=list)
    use_glossary: Mapped[bool] = mapped_column(Boolean, default=True)
    status: Mapped[str] = mapped_column(String(32), default="")
    stage: Mapped[str] = mapped_column(String(32), default="")
    detail: Mapped[str] = mapped_column(Text, default="")
    percent: Mapped[int] = mapped_column(Integer, default=0)
    error: Mapped[Optional[str]] = mapped_column(Text, default=None, nullable=True)
    result: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, default=None, nullable=True)
    glossary_data: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, default=None, nullable=True)
    glossary_exports: Mapped[Optional[dict[str, Any]]] = mapped_column(JSON, default=None, nullable=True)
    language_runs: Mapped[Optional[list[dict[str, Any]]]] = mapped_column(JSON, default=None, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow, index=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None, nullable=True)


# ── Terminology library ──────────────────────────────────────────────
class Domain(Base):
    __tablename__ = "domains"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    owner_id: Mapped[int] = mapped_column(Integer, default=0, index=True)  # 0 = shared
    name: Mapped[str] = mapped_column(String(64), index=True)
    name_en: Mapped[str] = mapped_column(String(128), default="")
    name_zh: Mapped[str] = mapped_column(String(128), default="")
    description: Mapped[str] = mapped_column(Text, default="")
    description_zh: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )

    terms: Mapped[list["LibraryTerm"]] = relationship(
        back_populates="domain",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    __table_args__ = (
        UniqueConstraint("owner_id", "name", name="uq_domain_owner_name"),
    )


class LibraryTerm(Base):
    __tablename__ = "library_terms"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    domain_id: Mapped[int] = mapped_column(
        ForeignKey("domains.id", ondelete="CASCADE"), index=True
    )
    source: Mapped[str] = mapped_column(String(512))
    source_normalized: Mapped[str] = mapped_column(String(512), index=True)
    targets: Mapped[dict[str, str]] = mapped_column(JSON, default=dict)
    strategy: Mapped[str] = mapped_column(String(32), default="hard")
    ai_category: Mapped[str] = mapped_column(String(64), default="")
    context: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), default=None, nullable=True)
    use_count: Mapped[int] = mapped_column(Integer, default=0)

    domain: Mapped["Domain"] = relationship(back_populates="terms")

    __table_args__ = (
        UniqueConstraint("domain_id", "source_normalized", name="uq_term_domain_source"),
    )
