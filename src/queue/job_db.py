"""Persistence for translation job history, backed by SQLAlchemy.

Uses SQLite locally (data/app.db) and Postgres in production via DATABASE_URL.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select

from src.db import session_scope
from src.db.models import Job

logger = logging.getLogger(__name__)


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value)
        except ValueError:
            return None
    return None


def _format_iso(value: datetime | None) -> str | None:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _dict_to_kwargs(job: dict) -> dict[str, Any]:
    """Convert the in-memory job dict to ORM column kwargs."""
    return {
        "owner_id": int(job.get("owner_id", 0)),
        "filename": job.get("filename", ""),
        "source_language": job.get("source_language", ""),
        "target_languages": job.get("target_languages") or [],
        "use_glossary": bool(job.get("use_glossary", True)),
        "status": job.get("status", ""),
        "stage": job.get("stage", ""),
        "detail": job.get("detail", ""),
        "percent": int(job.get("percent", 0)),
        "error": job.get("error"),
        "result": job.get("result"),
        # Dict uses "glossary"; column uses "glossary_data" to avoid confusion
        "glossary_data": job.get("glossary"),
        "glossary_exports": job.get("glossary_exports"),
        "language_runs": job.get("language_runs"),
        "created_at": _parse_iso(job.get("created_at")) or datetime.now(timezone.utc),
        "started_at": _parse_iso(job.get("started_at")),
        "completed_at": _parse_iso(job.get("completed_at")),
    }


def _orm_to_dict(j: Job) -> dict[str, Any]:
    return {
        "job_id": j.job_id,
        "owner_id": j.owner_id,
        "filename": j.filename,
        "source_language": j.source_language,
        "target_languages": j.target_languages or [],
        "use_glossary": bool(j.use_glossary),
        "status": j.status,
        "stage": j.stage,
        "detail": j.detail,
        "percent": int(j.percent),
        "error": j.error,
        "result": j.result,
        "glossary": j.glossary_data,
        "glossary_exports": j.glossary_exports or {},
        "language_runs": j.language_runs or [],
        "created_at": _format_iso(j.created_at),
        "started_at": _format_iso(j.started_at),
        "completed_at": _format_iso(j.completed_at),
    }


class JobDB:
    """ORM-backed history of translation jobs."""

    def __init__(self) -> None:
        # Engine and tables are created at server startup (lifespan).
        pass

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def save_job(self, job: dict) -> None:
        job_id = job.get("job_id")
        if not job_id:
            return
        kwargs = _dict_to_kwargs(job)
        with session_scope() as s:
            existing = s.get(Job, job_id)
            if existing is None:
                s.add(Job(job_id=job_id, **kwargs))
            else:
                for k, v in kwargs.items():
                    setattr(existing, k, v)

    def update_job(self, job_id: str, **fields: object) -> None:
        if not fields:
            return
        # Caller convention: dict uses "glossary", column is "glossary_data"
        if "glossary" in fields:
            fields["glossary_data"] = fields.pop("glossary")
        for ts in ("created_at", "started_at", "completed_at"):
            if ts in fields and isinstance(fields[ts], str):
                fields[ts] = _parse_iso(fields[ts])
        with session_scope() as s:
            existing = s.get(Job, job_id)
            if existing is None:
                return
            for k, v in fields.items():
                if hasattr(existing, k):
                    setattr(existing, k, v)

    def load_all(self) -> list[dict]:
        with session_scope() as s:
            stmt = select(Job).order_by(Job.created_at.desc())
            return [_orm_to_dict(j) for j in s.scalars(stmt).all()]

    def delete_job(self, job_id: str) -> None:
        with session_scope() as s:
            existing = s.get(Job, job_id)
            if existing is not None:
                s.delete(existing)
