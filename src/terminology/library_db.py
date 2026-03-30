"""SQLite-backed persistent terminology library.

Provides CRUD operations for domains and terms, matching for merge,
and bulk import/export support.
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

from src.utils.paths import get_data_dir

_DEFAULT_DB_PATH = get_data_dir() / "data" / "terminology.db"


class TermLibraryDB:
    """Low-level data access layer for the terminology library."""

    def __init__(self, db_path: str | Path | None = None) -> None:
        self._db_path = str(db_path or _DEFAULT_DB_PATH)
        self._lock = threading.Lock()
        self._ensure_schema()

    # ── schema ────────────────────────────────────────────────────

    def _get_conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        return conn

    def _ensure_schema(self) -> None:
        Path(self._db_path).parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            conn = self._get_conn()
            try:
                conn.executescript("""
                    CREATE TABLE IF NOT EXISTS domains (
                        id              INTEGER PRIMARY KEY AUTOINCREMENT,
                        name            TEXT NOT NULL UNIQUE,
                        name_en         TEXT NOT NULL DEFAULT '',
                        name_zh         TEXT NOT NULL DEFAULT '',
                        description     TEXT NOT NULL DEFAULT '',
                        description_zh  TEXT NOT NULL DEFAULT '',
                        created_at      TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at      TEXT NOT NULL DEFAULT (datetime('now'))
                    );

                    CREATE TABLE IF NOT EXISTS library_terms (
                        id                INTEGER PRIMARY KEY AUTOINCREMENT,
                        domain_id         INTEGER NOT NULL REFERENCES domains(id) ON DELETE CASCADE,
                        source            TEXT NOT NULL,
                        source_normalized TEXT NOT NULL,
                        targets           TEXT NOT NULL DEFAULT '{}',
                        strategy          TEXT NOT NULL DEFAULT 'hard',
                        ai_category       TEXT NOT NULL DEFAULT '',
                        context           TEXT NOT NULL DEFAULT '',
                        created_at        TEXT NOT NULL DEFAULT (datetime('now')),
                        updated_at        TEXT NOT NULL DEFAULT (datetime('now')),
                        last_used_at      TEXT,
                        use_count         INTEGER NOT NULL DEFAULT 0,
                        UNIQUE(domain_id, source_normalized)
                    );

                    CREATE INDEX IF NOT EXISTS idx_terms_domain
                        ON library_terms(domain_id);
                """)
                conn.commit()
                # Migration: add name_en/name_zh columns if missing
                for col in ("name_en", "name_zh", "description_zh"):
                    try:
                        conn.execute(f"ALTER TABLE domains ADD COLUMN {col} TEXT NOT NULL DEFAULT ''")
                        conn.commit()
                    except sqlite3.OperationalError:
                        pass  # column already exists
                self._seed_default_domains(conn)
            finally:
                conn.close()

    # ── seed default domains ─────────────────────────────────────

    # (name_key, name_en, name_zh, desc_en, desc_zh)
    _DEFAULT_DOMAINS: list[tuple[str, str, str, str, str]] = [
        ("economics_finance",    "Economics / Finance",    "经济/金融",  "Economics, finance, banking, insurance, investment, accounting", "经济、金融、银行、保险、投资、会计"),
        ("law",                  "Law",                    "法学",       "Legal, judicial, regulatory, compliance, legislation", "法律、司法、合规、立法"),
        ("medical",              "Medical",                "医药卫生",   "Healthcare, medicine, clinical, pharmaceutical, biomedical", "医疗、医学、临床、制药、生物医学"),
        ("information_technology","Information Technology", "信息技术",   "Software, computing, AI, cybersecurity, telecommunications", "软件、计算、人工智能、网络安全、通信"),
        ("engineering",          "Engineering",            "工程技术",   "Mechanical, civil, manufacturing, automotive, aerospace", "机械、土木、制造、汽车、航空航天"),
        ("natural_science",      "Natural Science",        "自然科学",   "Physics, chemistry, biology, mathematics, astronomy", "物理、化学、生物、数学、天文"),
        ("agriculture",          "Agriculture",            "农林牧渔",   "Farming, forestry, fishery, veterinary", "农业、林业、渔业、畜牧兽医"),
        ("energy_environment",   "Energy / Environment",   "能源/环境",  "Energy, environmental, nuclear, ecology, climate", "能源、环境、核能、生态、气候"),
        ("education",            "Education",              "教育",       "Academic, teaching, training, sports", "学术、教学、培训、体育"),
        ("politics_military",    "Politics / Military",    "政治/军事",  "Government, military, defense, diplomacy, policy", "政府、军事、国防、外交、政策"),
        ("social_science",       "Social Science",         "社会科学",   "Philosophy, sociology, psychology, history, religion", "哲学、社会学、心理学、历史、宗教"),
        ("literature_arts",      "Literature / Arts",      "文学/艺术",  "Literature, art, linguistics, culture, music, film", "文学、艺术、语言学、文化、音乐、电影"),
        ("media_communication",  "Media / Communication",  "新闻传媒",   "Journalism, media, communication, publishing", "新闻、媒体、传播、出版"),
        ("business",             "Business",               "商业/营销",  "Marketing, advertising, sales, e-commerce, retail", "营销、广告、销售、电商、零售"),
        ("general",              "General",                "通用",       "General-purpose terms not specific to any domain", "通用术语，不限定特定领域"),
    ]

    @classmethod
    def _seed_default_domains(cls, conn: sqlite3.Connection) -> None:
        """Ensure all 15 default domains exist."""
        # Insert any missing default domains
        for key, name_en, name_zh, desc_en, desc_zh in cls._DEFAULT_DOMAINS:
            conn.execute(
                "INSERT OR IGNORE INTO domains (name, name_en, name_zh, description, description_zh) VALUES (?, ?, ?, ?, ?)",
                (key, name_en, name_zh, desc_en, desc_zh),
            )

        # Backfill name_en/name_zh/description_zh for existing domains
        for key, name_en, name_zh, desc_en, desc_zh in cls._DEFAULT_DOMAINS:
            conn.execute(
                "UPDATE domains SET name_en = ?, name_zh = ?, description_zh = ? WHERE name = ? AND (name_en = '' OR name_zh = '' OR description_zh = '')",
                (name_en, name_zh, desc_zh, key),
            )

        conn.commit()

    # ── domain CRUD ───────────────────────────────────────────────

    def create_domain(self, name: str, description: str = "") -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    "INSERT INTO domains (name, description) VALUES (?, ?)",
                    (name.strip(), description.strip()),
                )
                conn.commit()
                return cur.lastrowid  # type: ignore[return-value]
            finally:
                conn.close()

    def list_domains(self) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute("""
                    SELECT d.*, COUNT(t.id) AS term_count
                    FROM domains d
                    LEFT JOIN library_terms t ON t.domain_id = d.id
                    GROUP BY d.id
                    ORDER BY d.name
                """).fetchall()
                return [dict(r) for r in rows]
            finally:
                conn.close()

    def get_domain(self, domain_id: int) -> dict | None:
        with self._lock:
            conn = self._get_conn()
            try:
                row = conn.execute(
                    """SELECT d.*, COUNT(t.id) AS term_count
                       FROM domains d
                       LEFT JOIN library_terms t ON t.domain_id = d.id
                       WHERE d.id = ?
                       GROUP BY d.id""",
                    (domain_id,),
                ).fetchone()
                return dict(row) if row else None
            finally:
                conn.close()

    def update_domain(
        self, domain_id: int, name: str | None = None, description: str | None = None
    ) -> bool:
        sets: list[str] = []
        params: list = []
        if name is not None:
            sets.append("name = ?")
            params.append(name.strip())
        if description is not None:
            sets.append("description = ?")
            params.append(description.strip())
        if not sets:
            return False
        sets.append("updated_at = datetime('now')")
        params.append(domain_id)

        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    f"UPDATE domains SET {', '.join(sets)} WHERE id = ?", params
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def delete_domain(self, domain_id: int) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute("DELETE FROM domains WHERE id = ?", (domain_id,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    # ── term CRUD ─────────────────────────────────────────────────

    @staticmethod
    def _normalize(source: str) -> str:
        return source.strip().lower()

    def upsert_term(
        self,
        domain_id: int,
        source: str,
        targets: dict[str, str],
        strategy: str = "hard",
        ai_category: str = "",
        context: str = "",
    ) -> int:
        normalized = self._normalize(source)

        with self._lock:
            conn = self._get_conn()
            try:
                existing = conn.execute(
                    "SELECT id, targets FROM library_terms WHERE domain_id = ? AND source_normalized = ?",
                    (domain_id, normalized),
                ).fetchone()

                if existing:
                    old_targets = json.loads(existing["targets"]) if existing["targets"] else {}
                    merged = {**old_targets}
                    for lang, val in targets.items():
                        if val:  # don't overwrite non-empty with empty
                            merged[lang] = val
                    merged_json = json.dumps(merged, ensure_ascii=False)
                    conn.execute(
                        """UPDATE library_terms
                           SET source = ?, targets = ?, strategy = ?,
                               ai_category = ?, context = ?, updated_at = datetime('now')
                           WHERE id = ?""",
                        (source.strip(), merged_json, strategy, ai_category, context, existing["id"]),
                    )
                    conn.commit()
                    return existing["id"]
                else:
                    clean = {k: v for k, v in targets.items() if v}
                    clean_json = json.dumps(clean, ensure_ascii=False)
                    cur = conn.execute(
                        """INSERT INTO library_terms
                               (domain_id, source, source_normalized, targets, strategy, ai_category, context)
                           VALUES (?, ?, ?, ?, ?, ?, ?)""",
                        (domain_id, source.strip(), normalized, clean_json, strategy, ai_category, context),
                    )
                    conn.commit()
                    return cur.lastrowid  # type: ignore[return-value]
            finally:
                conn.close()

    def get_terms_by_domain(
        self,
        domain_id: int,
        search: str = "",
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        with self._lock:
            conn = self._get_conn()
            try:
                if search:
                    pattern = f"%{search.strip().lower()}%"
                    rows = conn.execute(
                        """SELECT * FROM library_terms
                           WHERE domain_id = ? AND source_normalized LIKE ?
                           ORDER BY source_normalized
                           LIMIT ? OFFSET ?""",
                        (domain_id, pattern, limit, offset),
                    ).fetchall()
                else:
                    rows = conn.execute(
                        """SELECT * FROM library_terms
                           WHERE domain_id = ?
                           ORDER BY source_normalized
                           LIMIT ? OFFSET ?""",
                        (domain_id, limit, offset),
                    ).fetchall()
                return [self._row_to_dict(r) for r in rows]
            finally:
                conn.close()

    def count_terms_by_domain(self, domain_id: int, search: str = "") -> int:
        with self._lock:
            conn = self._get_conn()
            try:
                if search:
                    pattern = f"%{search.strip().lower()}%"
                    row = conn.execute(
                        "SELECT COUNT(*) FROM library_terms WHERE domain_id = ? AND source_normalized LIKE ?",
                        (domain_id, pattern),
                    ).fetchone()
                else:
                    row = conn.execute(
                        "SELECT COUNT(*) FROM library_terms WHERE domain_id = ?",
                        (domain_id,),
                    ).fetchone()
                return row[0] if row else 0
            finally:
                conn.close()

    def update_term(self, term_id: int, **fields: str | dict) -> bool:
        allowed = {"source", "targets", "strategy", "ai_category", "context"}
        sets: list[str] = []
        params: list = []

        with self._lock:
            conn = self._get_conn()
            try:
                # If targets is being updated, merge with existing
                if "targets" in fields and isinstance(fields["targets"], dict):
                    existing = conn.execute(
                        "SELECT targets FROM library_terms WHERE id = ?", (term_id,)
                    ).fetchone()
                    if existing:
                        old_targets = json.loads(existing["targets"]) if existing["targets"] else {}
                        merged = {**old_targets}
                        for lang, val in fields["targets"].items():
                            if val:  # don't overwrite non-empty with empty
                                merged[lang] = val
                            elif lang in merged and not val:
                                # Allow explicit clearing by setting empty string
                                merged[lang] = val
                        fields = dict(fields)
                        fields["targets"] = merged

                for key, value in fields.items():
                    if key not in allowed:
                        continue
                    if key == "source":
                        sets.append("source = ?")
                        params.append(value)
                        sets.append("source_normalized = ?")
                        params.append(self._normalize(str(value)))
                    elif key == "targets":
                        sets.append("targets = ?")
                        params.append(json.dumps(value, ensure_ascii=False) if isinstance(value, dict) else value)
                    else:
                        sets.append(f"{key} = ?")
                        params.append(value)
                if not sets:
                    return False
                sets.append("updated_at = datetime('now')")
                params.append(term_id)

                cur = conn.execute(
                    f"UPDATE library_terms SET {', '.join(sets)} WHERE id = ?", params
                )
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def delete_term(self, term_id: int) -> bool:
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute("DELETE FROM library_terms WHERE id = ?", (term_id,))
                conn.commit()
                return cur.rowcount > 0
            finally:
                conn.close()

    def delete_terms_batch(self, term_ids: list[int]) -> int:
        if not term_ids:
            return 0
        placeholders = ",".join("?" for _ in term_ids)
        with self._lock:
            conn = self._get_conn()
            try:
                cur = conn.execute(
                    f"DELETE FROM library_terms WHERE id IN ({placeholders})", term_ids
                )
                conn.commit()
                return cur.rowcount
            finally:
                conn.close()

    # ── matching & bulk ───────────────────────────────────────────

    def find_matching_terms(
        self, sources: list[str], domain_ids: list[int] | None = None
    ) -> dict[str, dict]:
        """Find library terms matching the given source strings.

        Returns a dict keyed by source_normalized -> term dict.
        """
        if not sources:
            return {}
        normalized = [self._normalize(s) for s in sources]
        placeholders = ",".join("?" for _ in normalized)

        with self._lock:
            conn = self._get_conn()
            try:
                if domain_ids:
                    domain_ph = ",".join("?" for _ in domain_ids)
                    rows = conn.execute(
                        f"""SELECT * FROM library_terms
                            WHERE source_normalized IN ({placeholders})
                            AND domain_id IN ({domain_ph})
                            ORDER BY domain_id""",
                        [*normalized, *domain_ids],
                    ).fetchall()
                else:
                    rows = conn.execute(
                        f"""SELECT * FROM library_terms
                            WHERE source_normalized IN ({placeholders})""",
                        normalized,
                    ).fetchall()

                # First match wins (ordered by domain_id priority)
                result: dict[str, dict] = {}
                for row in rows:
                    key = row["source_normalized"]
                    if key not in result:
                        result[key] = self._row_to_dict(row)
                return result
            finally:
                conn.close()

    def get_all_terms_by_domains(self, domain_ids: list[int]) -> list[dict]:
        """Get all terms from the given domains (for supplement injection)."""
        if not domain_ids:
            return []
        placeholders = ",".join("?" for _ in domain_ids)
        with self._lock:
            conn = self._get_conn()
            try:
                rows = conn.execute(
                    f"""SELECT * FROM library_terms
                        WHERE domain_id IN ({placeholders})
                        ORDER BY LENGTH(source) DESC""",
                    domain_ids,
                ).fetchall()
                return [self._row_to_dict(r) for r in rows]
            finally:
                conn.close()

    def bulk_upsert(self, domain_id: int, terms: list[dict]) -> tuple[int, int]:
        """Bulk upsert terms. Returns (inserted, updated)."""
        if not terms:
            return 0, 0

        inserted = 0
        updated = 0
        with self._lock:
            conn = self._get_conn()
            try:
                for term in terms:
                    source = term.get("source", "").strip()
                    if not source:
                        continue
                    normalized = self._normalize(source)
                    targets = term.get("targets", {})

                    # Check if exists and merge targets
                    existing = conn.execute(
                        "SELECT id, targets FROM library_terms WHERE domain_id = ? AND source_normalized = ?",
                        (domain_id, normalized),
                    ).fetchone()

                    if existing:
                        old_targets = json.loads(existing["targets"]) if existing["targets"] else {}
                        merged = {**old_targets}
                        for lang, val in targets.items():
                            if val:
                                merged[lang] = val
                        merged_json = json.dumps(merged, ensure_ascii=False)
                        conn.execute(
                            """UPDATE library_terms
                               SET source = ?, targets = ?, strategy = ?,
                                   ai_category = ?, context = ?, updated_at = datetime('now')
                               WHERE id = ?""",
                            (
                                source,
                                merged_json,
                                term.get("strategy", "hard"),
                                term.get("ai_category", ""),
                                term.get("context", ""),
                                existing["id"],
                            ),
                        )
                        updated += 1
                    else:
                        clean = {k: v for k, v in targets.items() if v}
                        clean_json = json.dumps(clean, ensure_ascii=False)
                        conn.execute(
                            """INSERT INTO library_terms
                                   (domain_id, source, source_normalized, targets, strategy, ai_category, context)
                               VALUES (?, ?, ?, ?, ?, ?, ?)""",
                            (
                                domain_id,
                                source,
                                normalized,
                                clean_json,
                                term.get("strategy", "hard"),
                                term.get("ai_category", ""),
                                term.get("context", ""),
                            ),
                        )
                        inserted += 1

                conn.commit()
                return inserted, updated
            finally:
                conn.close()

    def export_domain(self, domain_id: int) -> list[dict]:
        """Export all terms in a domain."""
        return self.get_terms_by_domain(domain_id, limit=999999)

    def touch_terms(self, term_ids: list[int]) -> None:
        """Update last_used_at and increment use_count for the given terms."""
        if not term_ids:
            return
        placeholders = ",".join("?" for _ in term_ids)
        now = datetime.now(timezone.utc).isoformat()
        with self._lock:
            conn = self._get_conn()
            try:
                conn.execute(
                    f"""UPDATE library_terms
                        SET last_used_at = ?, use_count = use_count + 1
                        WHERE id IN ({placeholders})""",
                    [now, *term_ids],
                )
                conn.commit()
            finally:
                conn.close()

    # ── bidirectional matching ─────────────────────────────────────

    def find_matching_terms_bidirectional(
        self, search_terms: list[str], domain_ids: list[int] | None = None
    ) -> dict[str, dict]:
        """Search both source_normalized and all target values.

        Returns {normalized_search_term: matching term dict}.
        """
        if not search_terms:
            return {}
        normalized_terms = [self._normalize(s) for s in search_terms]

        # Load all terms from the given domains
        all_terms = self.get_all_terms_by_domains(domain_ids or [])
        if not all_terms:
            return {}

        # Build indexes: by source and by target value
        by_source: dict[str, dict] = {}
        by_target: dict[str, dict] = {}
        for t in all_terms:
            by_source[t["source_normalized"]] = t
            for val in t.get("targets", {}).values():
                if val:
                    val_norm = val.strip().lower()
                    if val_norm not in by_target:
                        by_target[val_norm] = t

        result: dict[str, dict] = {}
        for norm in normalized_terms:
            if norm not in result:
                match = by_source.get(norm) or by_target.get(norm)
                if match:
                    result[norm] = match
        return result

    def find_term_by_any_value(
        self, value: str, domain_id: int
    ) -> dict | None:
        """Find a term where source or any target value matches (for dedup on save)."""
        normalized = self._normalize(value)
        with self._lock:
            conn = self._get_conn()
            try:
                # Check source_normalized first
                row = conn.execute(
                    "SELECT * FROM library_terms WHERE domain_id = ? AND source_normalized = ?",
                    (domain_id, normalized),
                ).fetchone()
                if row:
                    return self._row_to_dict(row)

                # Scan targets values
                rows = conn.execute(
                    "SELECT * FROM library_terms WHERE domain_id = ?",
                    (domain_id,),
                ).fetchall()
                for r in rows:
                    targets = json.loads(r["targets"]) if r["targets"] else {}
                    for val in targets.values():
                        if val and val.strip().lower() == normalized:
                            return self._row_to_dict(r)
                return None
            finally:
                conn.close()

    # ── helpers ───────────────────────────────────────────────────

    @staticmethod
    def _row_to_dict(row: sqlite3.Row) -> dict:
        d = dict(row)
        # Parse targets JSON string back to dict
        if "targets" in d and isinstance(d["targets"], str):
            try:
                d["targets"] = json.loads(d["targets"])
            except (json.JSONDecodeError, TypeError):
                d["targets"] = {}
        return d
