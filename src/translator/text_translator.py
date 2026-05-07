"""Lightweight text-only translator.

Used by POST /api/text/translate. Bypasses file parsing/rebuild but reuses
the translator agent's prompt template, glossary constraint formatting,
and marker-based response parsing for consistency with file translation.
"""

from __future__ import annotations

import logging
import time
from typing import Optional

from src.llm.sudo_client import get_client
from src.models.content import BlockType, ContentBlock
from src.models.glossary import Glossary, GlossaryTerm
from src.terminology.library_db import TermLibraryDB
from src.translator.agent import (
    _build_marked_input,
    _build_marked_review_input,
    _load_prompt_template,
    _load_review_template,
    _parse_marked_response,
)
from src.utils.language_detect import LANGUAGE_NAMES_EN, detect_language

logger = logging.getLogger(__name__)


def _build_glossary_from_library(target_language: str) -> Glossary:
    """Auto-load all hard / keep_original terms from the term library.

    Only includes terms relevant to the target language so the prompt
    doesn't blow up on a bilingual library.
    """
    db = TermLibraryDB()
    domain_ids = [d["id"] for d in db.list_domains()]
    if not domain_ids:
        return Glossary(terms=[], target_language=target_language)

    raw_terms = db.get_all_terms_by_domains(domain_ids)
    terms: list[GlossaryTerm] = []
    for t in raw_terms:
        strategy = t.get("strategy", "hard")
        if strategy == "skip":
            continue
        targets = t.get("targets") or {}
        if strategy == "hard" and not targets.get(target_language):
            # No translation for this language — skip the term
            continue
        terms.append(GlossaryTerm(
            id=str(t["id"]),
            source=t["source"],
            targets=targets,
            strategy=strategy,
            context=t.get("context", ""),
            confirmed=True,
        ))
    return Glossary(terms=terms, target_language=target_language)


async def translate_text(
    text: str,
    target_language: str,
    *,
    review: bool = True,
    source_language: Optional[str] = None,
) -> dict:
    """Translate a piece of text.

    Returns dict with: translated, source_language, elapsed_seconds.
    Raises on LLM failure (caller decides 5xx vs 4xx mapping).
    """
    started = time.time()

    if not text.strip():
        return {
            "translated": "",
            "source_language": source_language or "",
            "elapsed_seconds": 0.0,
        }

    src_lang = source_language or detect_language(text) or "auto"
    src_lang_name = LANGUAGE_NAMES_EN.get(src_lang.lower(), src_lang)
    tgt_lang_name = LANGUAGE_NAMES_EN.get(target_language.lower(), target_language)

    glossary = _build_glossary_from_library(target_language)
    constraints = (
        glossary.to_constraint_text(target_language=target_language)
        or "No terminology constraints."
    )

    block = ContentBlock(id="t1", type=BlockType.PARAGRAPH, source_text=text)
    client = get_client()

    # ── Phase 1: translation ────────────────────────────────────────
    template = _load_prompt_template()
    system_message = template.format(
        source_language_name=src_lang_name,
        target_language_name=tgt_lang_name,
        glossary_constraints=constraints,
        context_hint="(none — single text input)",
    )
    user_message = _build_marked_input([block])

    response = await client.simple_chat(
        user_message=user_message,
        system_message=system_message,
        temperature=0.5,
        model=client.get_model("translation"),
    )
    _parse_marked_response(response, [block])
    if not block.translated_text:
        # Marker not found — fall back to the raw response (LLM ignored marker)
        block.translated_text = response.strip()

    # ── Phase 2: naturalness review (optional) ───────────────────────
    if review and block.translated_text:
        review_template = _load_review_template()
        review_system = review_template.format(
            source_language_name=src_lang_name,
            target_language_name=tgt_lang_name,
            glossary_constraints=constraints,
            language_structural_notes="",
        )
        review_user = _build_marked_review_input([block])
        try:
            review_response = await client.simple_chat(
                user_message=review_user,
                system_message=review_system,
                temperature=0.7,
                model=client.get_model("review"),
            )
            original = block.translated_text
            _parse_marked_response(review_response, [block])
            if not block.translated_text:
                # Reviewer dropped the marker — keep the draft
                block.translated_text = original
        except Exception as exc:  # noqa: BLE001
            logger.warning("Naturalness review failed, keeping draft: %s", exc)

    return {
        "translated": block.translated_text or "",
        "source_language": src_lang,
        "elapsed_seconds": time.time() - started,
    }
