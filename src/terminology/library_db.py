"""Terminology library backed by SQLAlchemy ORM.

Provides the same public surface as the previous sqlite3 version. All data
lives in the unified app.db (SQLite) or Postgres database (production).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select, update

from src.db import session_scope
from src.db.models import Domain, LibraryTerm

logger = logging.getLogger(__name__)


# (key, name_en, name_zh, desc_en, desc_zh)
_DEFAULT_DOMAINS: list[tuple[str, str, str, str, str]] = [
    ("economics_finance",     "Economics / Finance",    "经济/金融",  "Economics, finance, banking, insurance, investment, accounting", "经济、金融、银行、保险、投资、会计"),
    ("law",                   "Law",                    "法学",       "Legal, judicial, regulatory, compliance, legislation", "法律、司法、合规、立法"),
    ("medical",               "Medical",                "医药卫生",   "Healthcare, medicine, clinical, pharmaceutical, biomedical", "医疗、医学、临床、制药、生物医学"),
    ("information_technology", "Information Technology", "信息技术",   "Software, computing, AI, cybersecurity, telecommunications", "软件、计算、人工智能、网络安全、通信"),
    ("engineering",           "Engineering",            "工程技术",   "Mechanical, civil, manufacturing, automotive, aerospace", "机械、土木、制造、汽车、航空航天"),
    ("natural_science",       "Natural Science",        "自然科学",   "Physics, chemistry, biology, mathematics, astronomy", "物理、化学、生物、数学、天文"),
    ("agriculture",           "Agriculture",            "农林牧渔",   "Farming, forestry, fishery, veterinary", "农业、林业、渔业、畜牧兽医"),
    ("energy_environment",    "Energy / Environment",   "能源/环境",  "Energy, environmental, nuclear, ecology, climate", "能源、环境、核能、生态、气候"),
    ("education",             "Education",              "教育",       "Academic, teaching, training, sports", "学术、教学、培训、体育"),
    ("politics_military",     "Politics / Military",    "政治/军事",  "Government, military, defense, diplomacy, policy", "政府、军事、国防、外交、政策"),
    ("social_science",        "Social Science",         "社会科学",   "Philosophy, sociology, psychology, history, religion", "哲学、社会学、心理学、历史、宗教"),
    ("literature_arts",       "Literature / Arts",      "文学/艺术",  "Literature, art, linguistics, culture, music, film", "文学、艺术、语言学、文化、音乐、电影"),
    ("media_communication",   "Media / Communication",  "新闻传媒",   "Journalism, media, communication, publishing", "新闻、媒体、传播、出版"),
    ("business",              "Business",               "商业/营销",  "Marketing, advertising, sales, e-commerce, retail", "营销、广告、销售、电商、零售"),
    ("general",               "General",                "通用",       "General-purpose terms not specific to any domain", "通用术语，不限定特定领域"),
]


def seed_default_domains() -> None:
    """Insert the 15 standard domains if missing. Idempotent."""
    with session_scope() as s:
        existing_names = set(
            s.execute(
                select(Domain.name).where(Domain.owner_id == 0)
            ).scalars().all()
        )
        for key, name_en, name_zh, desc_en, desc_zh in _DEFAULT_DOMAINS:
            if key in existing_names:
                continue
            s.add(Domain(
                owner_id=0,
                name=key,
                name_en=name_en,
                name_zh=name_zh,
                description=desc_en,
                description_zh=desc_zh,
            ))


def _format_iso(value: datetime | None) -> str | None:
    if not value:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.isoformat()


def _domain_to_dict(d: Domain, term_count: int = 0) -> dict[str, Any]:
    return {
        "id": d.id,
        "owner_id": d.owner_id,
        "name": d.name,
        "name_en": d.name_en,
        "name_zh": d.name_zh,
        "description": d.description,
        "description_zh": d.description_zh,
        "created_at": _format_iso(d.created_at),
        "updated_at": _format_iso(d.updated_at),
        "term_count": int(term_count or 0),
    }


def _term_to_dict(t: LibraryTerm) -> dict[str, Any]:
    return {
        "id": t.id,
        "domain_id": t.domain_id,
        "source": t.source,
        "source_normalized": t.source_normalized,
        "targets": t.targets or {},
        "strategy": t.strategy,
        "ai_category": t.ai_category,
        "context": t.context,
        "created_at": _format_iso(t.created_at),
        "updated_at": _format_iso(t.updated_at),
        "last_used_at": _format_iso(t.last_used_at),
        "use_count": t.use_count,
    }


class TermLibraryDB:
    """ORM-backed CRUD for the terminology library."""

    def __init__(self) -> None:
        # Engine and tables are created at server startup (lifespan).
        pass

    @staticmethod
    def _normalize(source: str) -> str:
        return source.strip().lower()

    # ── domain CRUD ───────────────────────────────────────────────

    def create_domain(self, name: str, description: str = "") -> int:
        with session_scope() as s:
            d = Domain(
                owner_id=0,
                name=name.strip(),
                description=description.strip(),
            )
            s.add(d)
            s.flush()
            return d.id

    def list_domains(self) -> list[dict]:
        with session_scope() as s:
            stmt = (
                select(Domain, func.count(LibraryTerm.id).label("term_count"))
                .outerjoin(LibraryTerm, LibraryTerm.domain_id == Domain.id)
                .group_by(Domain.id)
                .order_by(Domain.name)
            )
            return [
                _domain_to_dict(d, count)
                for d, count in s.execute(stmt).all()
            ]

    def get_domain(self, domain_id: int) -> dict | None:
        with session_scope() as s:
            stmt = (
                select(Domain, func.count(LibraryTerm.id).label("term_count"))
                .outerjoin(LibraryTerm, LibraryTerm.domain_id == Domain.id)
                .where(Domain.id == domain_id)
                .group_by(Domain.id)
            )
            row = s.execute(stmt).first()
            if row is None:
                return None
            return _domain_to_dict(row[0], row[1])

    def update_domain(
        self,
        domain_id: int,
        name: str | None = None,
        description: str | None = None,
    ) -> bool:
        if name is None and description is None:
            return False
        with session_scope() as s:
            d = s.get(Domain, domain_id)
            if d is None:
                return False
            if name is not None:
                d.name = name.strip()
            if description is not None:
                d.description = description.strip()
            return True

    def delete_domain(self, domain_id: int) -> bool:
        with session_scope() as s:
            d = s.get(Domain, domain_id)
            if d is None:
                return False
            s.delete(d)
            return True

    # ── term CRUD ─────────────────────────────────────────────────

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
        with session_scope() as s:
            existing = s.scalars(
                select(LibraryTerm).where(
                    LibraryTerm.domain_id == domain_id,
                    LibraryTerm.source_normalized == normalized,
                )
            ).first()
            if existing:
                merged = dict(existing.targets or {})
                for lang, val in (targets or {}).items():
                    if val:
                        merged[lang] = val
                existing.source = source.strip()
                existing.targets = merged
                existing.strategy = strategy
                existing.ai_category = ai_category
                existing.context = context
                s.flush()
                return existing.id
            clean = {k: v for k, v in (targets or {}).items() if v}
            term = LibraryTerm(
                domain_id=domain_id,
                source=source.strip(),
                source_normalized=normalized,
                targets=clean,
                strategy=strategy,
                ai_category=ai_category,
                context=context,
            )
            s.add(term)
            s.flush()
            return term.id

    def get_terms_by_domain(
        self,
        domain_id: int,
        search: str = "",
        offset: int = 0,
        limit: int = 100,
    ) -> list[dict]:
        with session_scope() as s:
            stmt = select(LibraryTerm).where(LibraryTerm.domain_id == domain_id)
            if search:
                pattern = f"%{search.strip().lower()}%"
                stmt = stmt.where(LibraryTerm.source_normalized.like(pattern))
            stmt = stmt.order_by(LibraryTerm.source_normalized).offset(offset).limit(limit)
            return [_term_to_dict(t) for t in s.scalars(stmt).all()]

    def count_terms_by_domain(self, domain_id: int, search: str = "") -> int:
        with session_scope() as s:
            stmt = select(func.count()).select_from(LibraryTerm).where(
                LibraryTerm.domain_id == domain_id
            )
            if search:
                pattern = f"%{search.strip().lower()}%"
                stmt = stmt.where(LibraryTerm.source_normalized.like(pattern))
            return int(s.execute(stmt).scalar_one())

    def update_term(self, term_id: int, **fields: object) -> bool:
        allowed = {"source", "targets", "strategy", "ai_category", "context"}
        fields = {k: v for k, v in fields.items() if k in allowed}
        if not fields:
            return False
        with session_scope() as s:
            t = s.get(LibraryTerm, term_id)
            if t is None:
                return False
            if "targets" in fields and isinstance(fields["targets"], dict):
                merged = dict(t.targets or {})
                for lang, val in fields["targets"].items():
                    # empty val explicitly clears, non-empty overwrites
                    if val or lang in merged:
                        merged[lang] = val
                t.targets = merged
                del fields["targets"]
            if "source" in fields:
                src = str(fields.pop("source"))
                t.source = src
                t.source_normalized = self._normalize(src)
            for k, v in fields.items():
                setattr(t, k, v)
            return True

    def delete_term(self, term_id: int) -> bool:
        with session_scope() as s:
            t = s.get(LibraryTerm, term_id)
            if t is None:
                return False
            s.delete(t)
            return True

    def delete_terms_batch(self, term_ids: list[int]) -> int:
        if not term_ids:
            return 0
        with session_scope() as s:
            count = s.execute(
                select(func.count())
                .select_from(LibraryTerm)
                .where(LibraryTerm.id.in_(term_ids))
            ).scalar_one()
            s.execute(
                LibraryTerm.__table__.delete().where(LibraryTerm.id.in_(term_ids))
            )
            return int(count)

    # ── matching & bulk ───────────────────────────────────────────

    def find_matching_terms(
        self, sources: list[str], domain_ids: list[int] | None = None
    ) -> dict[str, dict]:
        if not sources:
            return {}
        normalized = [self._normalize(s) for s in sources]
        with session_scope() as s:
            stmt = select(LibraryTerm).where(
                LibraryTerm.source_normalized.in_(normalized)
            )
            if domain_ids:
                stmt = stmt.where(LibraryTerm.domain_id.in_(domain_ids))
            stmt = stmt.order_by(LibraryTerm.domain_id)
            result: dict[str, dict] = {}
            for row in s.scalars(stmt).all():
                if row.source_normalized not in result:
                    result[row.source_normalized] = _term_to_dict(row)
            return result

    def get_all_terms_by_domains(self, domain_ids: list[int]) -> list[dict]:
        if not domain_ids:
            return []
        with session_scope() as s:
            stmt = (
                select(LibraryTerm)
                .where(LibraryTerm.domain_id.in_(domain_ids))
                .order_by(func.length(LibraryTerm.source).desc())
            )
            return [_term_to_dict(t) for t in s.scalars(stmt).all()]

    def bulk_upsert(self, domain_id: int, terms: list[dict]) -> tuple[int, int]:
        if not terms:
            return 0, 0
        inserted = updated = 0
        with session_scope() as s:
            for td in terms:
                source = (td.get("source") or "").strip()
                if not source:
                    continue
                normalized = self._normalize(source)
                targets = td.get("targets") or {}
                existing = s.scalars(
                    select(LibraryTerm).where(
                        LibraryTerm.domain_id == domain_id,
                        LibraryTerm.source_normalized == normalized,
                    )
                ).first()
                if existing:
                    merged = dict(existing.targets or {})
                    for lang, val in targets.items():
                        if val:
                            merged[lang] = val
                    existing.source = source
                    existing.targets = merged
                    existing.strategy = td.get("strategy", "hard")
                    existing.ai_category = td.get("ai_category", "")
                    existing.context = td.get("context", "")
                    updated += 1
                else:
                    clean = {k: v for k, v in targets.items() if v}
                    s.add(LibraryTerm(
                        domain_id=domain_id,
                        source=source,
                        source_normalized=normalized,
                        targets=clean,
                        strategy=td.get("strategy", "hard"),
                        ai_category=td.get("ai_category", ""),
                        context=td.get("context", ""),
                    ))
                    inserted += 1
        return inserted, updated

    def export_domain(self, domain_id: int) -> list[dict]:
        return self.get_terms_by_domain(domain_id, limit=10**9)

    def touch_terms(self, term_ids: list[int]) -> None:
        if not term_ids:
            return
        now = datetime.now(timezone.utc)
        with session_scope() as s:
            s.execute(
                update(LibraryTerm)
                .where(LibraryTerm.id.in_(term_ids))
                .values(
                    last_used_at=now,
                    use_count=LibraryTerm.use_count + 1,
                )
            )

    # ── bidirectional matching ────────────────────────────────────

    def find_matching_terms_bidirectional(
        self, search_terms: list[str], domain_ids: list[int] | None = None
    ) -> dict[str, dict]:
        if not search_terms:
            return {}
        normalized_terms = [self._normalize(s) for s in search_terms]
        all_terms = self.get_all_terms_by_domains(domain_ids or [])
        if not all_terms:
            return {}
        by_source: dict[str, dict] = {}
        by_target: dict[str, dict] = {}
        for t in all_terms:
            by_source[t["source_normalized"]] = t
            for val in (t.get("targets") or {}).values():
                if val:
                    vn = val.strip().lower()
                    if vn not in by_target:
                        by_target[vn] = t
        result: dict[str, dict] = {}
        for n in normalized_terms:
            if n in result:
                continue
            m = by_source.get(n) or by_target.get(n)
            if m:
                result[n] = m
        return result

    def find_term_by_any_value(self, value: str, domain_id: int) -> dict | None:
        normalized = self._normalize(value)
        with session_scope() as s:
            row = s.scalars(
                select(LibraryTerm).where(
                    LibraryTerm.domain_id == domain_id,
                    LibraryTerm.source_normalized == normalized,
                )
            ).first()
            if row:
                return _term_to_dict(row)
            for r in s.scalars(
                select(LibraryTerm).where(LibraryTerm.domain_id == domain_id)
            ).all():
                for val in (r.targets or {}).values():
                    if val and val.strip().lower() == normalized:
                        return _term_to_dict(r)
            return None
