from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from src.models.glossary import Glossary, GlossaryTerm

logger = logging.getLogger(__name__)


class GlossaryManager:
    """CRUD operations on a Glossary instance."""

    @staticmethod
    def create_from_terms(
        terms: list[GlossaryTerm],
        source_lang: str,
        target_langs: list[str],
    ) -> Glossary:
        return Glossary(
            glossary_id=uuid.uuid4().hex[:12],
            source_language=source_lang,
            target_languages=list(target_langs),
            terms=list(terms),
            created_at=datetime.now(timezone.utc).isoformat(),
        )

    @staticmethod
    def confirm_term(glossary: Glossary, term_id: str) -> None:
        for t in glossary.terms:
            if t.id == term_id:
                t.confirmed = True
                return
        logger.warning("Term %s not found in glossary", term_id)

    @staticmethod
    def confirm_all(glossary: Glossary) -> None:
        for t in glossary.terms:
            t.confirmed = True
        glossary.confirmed = True

    @staticmethod
    def update_term(
        glossary: Glossary,
        term_id: str,
        new_target: str,
        target_language: str | None = None,
    ) -> None:
        for t in glossary.terms:
            if t.id == term_id:
                target_key = target_language or glossary.target_language or "default"
                t.set_target(target_key, new_target)
                return
        logger.warning("Term %s not found in glossary", term_id)

    @staticmethod
    def remove_term(glossary: Glossary, term_id: str) -> None:
        before = len(glossary.terms)
        glossary.terms = [t for t in glossary.terms if t.id != term_id]
        if len(glossary.terms) == before:
            logger.warning("Term %s not found in glossary", term_id)

    @staticmethod
    def add_term(
        glossary: Glossary,
        source: str,
        target: str,
        category: str = "",
        target_language: str | None = None,
    ) -> GlossaryTerm:
        max_idx = 0
        for t in glossary.terms:
            if t.id.startswith("term_"):
                try:
                    max_idx = max(max_idx, int(t.id.split("_")[1]))
                except (IndexError, ValueError):
                    pass
        new_id = f"term_{max_idx + 1:03d}"
        target_key = target_language or glossary.target_language or "default"
        term = GlossaryTerm(
            id=new_id,
            source=source,
            targets={target_key: target},
            category=category,
        )
        glossary.terms.append(term)
        return term
