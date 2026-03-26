"""SQLite-backed persistence for translation job history."""

from __future__ import annotations

import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "jobs.db"


class JobDB:
    """Persists completed/errored jobs so they survive server restarts."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or _DEFAULT_DB_PATH)
        self._lock = threading.Lock()
        self._ensure_schema()

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        return conn

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = self._get_conn()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS jobs (
                        job_id          TEXT PRIMARY KEY,
                        filename        TEXT NOT NULL DEFAULT '',
                        source_language TEXT NOT NULL DEFAULT '',
                        target_languages TEXT NOT NULL DEFAULT '[]',
                        use_glossary    INTEGER NOT NULL DEFAULT 1,
                        status          TEXT NOT NULL DEFAULT '',
                        stage           TEXT NOT NULL DEFAULT '',
                        detail          TEXT NOT NULL DEFAULT '',
                        percent         INTEGER NOT NULL DEFAULT 0,
                        error           TEXT,
                        result          TEXT,
                        created_at      TEXT,
                        started_at      TEXT,
                        completed_at    TEXT
                    );
                """)
                conn.commit()
            finally:
                conn.close()

    @staticmethod
    def now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    def save_job(self, job: dict) -> None:
        """Insert or replace a job record."""
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    """INSERT OR REPLACE INTO jobs
                       (job_id, filename, source_language, target_languages,
                        use_glossary, status, stage, detail, percent,
                        error, result, created_at, started_at, completed_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (
                        job.get("job_id"),
                        job.get("filename", ""),
                        job.get("source_language", ""),
                        json.dumps(job.get("target_languages", []), ensure_ascii=False),
                        1 if job.get("use_glossary") else 0,
                        job.get("status", ""),
                        job.get("stage", ""),
                        job.get("detail", ""),
                        job.get("percent", 0),
                        job.get("error"),
                        json.dumps(job.get("result"), ensure_ascii=False) if job.get("result") else None,
                        job.get("created_at"),
                        job.get("started_at"),
                        job.get("completed_at"),
                    ),
                )
                conn.commit()
            finally:
                conn.close()

    def update_job(self, job_id: str, **fields: object) -> None:
        """Update specific fields of an existing job record."""
        if not fields:
            return
        # Serialize JSON fields
        if "target_languages" in fields:
            fields["target_languages"] = json.dumps(fields["target_languages"], ensure_ascii=False)
        if "result" in fields and fields["result"] is not None:
            fields["result"] = json.dumps(fields["result"], ensure_ascii=False)

        set_clause = ", ".join(f"{k} = ?" for k in fields)
        values = list(fields.values()) + [job_id]
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(f"UPDATE jobs SET {set_clause} WHERE job_id = ?", values)
                conn.commit()
            finally:
                conn.close()

    def load_all(self) -> list[dict]:
        """Load all persisted jobs, newest first."""
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    "SELECT * FROM jobs ORDER BY created_at DESC"
                ).fetchall()
            finally:
                conn.close()

        result = []
        for row in rows:
            job = dict(row)
            # Deserialize JSON fields
            try:
                job["target_languages"] = json.loads(job.get("target_languages") or "[]")
            except (json.JSONDecodeError, TypeError):
                job["target_languages"] = []
            try:
                job["result"] = json.loads(job["result"]) if job.get("result") else None
            except (json.JSONDecodeError, TypeError):
                job["result"] = None
            job["use_glossary"] = bool(job.get("use_glossary"))
            result.append(job)
        return result

    def delete_job(self, job_id: str) -> None:
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute("DELETE FROM jobs WHERE job_id = ?", (job_id,))
                conn.commit()
            finally:
                conn.close()
