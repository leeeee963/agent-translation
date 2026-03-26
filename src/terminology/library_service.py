"""Business logic for the terminology library.

Provides merge algorithm, supplement injection, save-back, and import/export.
"""

from __future__ import annotations

import csv
import io
import json
import logging
import re
from copy import deepcopy

from src.models.glossary import Glossary, GlossaryTerm
from src.terminology.library_db import TermLibraryDB

logger = logging.getLogger(__name__)


class TermLibraryService:
    """High-level operations for the terminology library."""

    def __init__(self, db: TermLibraryDB | None = None) -> None:
        self._db = db or TermLibraryDB()

    # ── merge algorithm ───────────────────────────────────────────

    def merge_with_extracted(
        self,
        extracted_glossary: Glossary,
        domain_ids: list[int],
        source_text: str = "",
        target_languages: list[str] | None = None,
    ) -> Glossary:
        """Merge LLM-extracted terms with library terms.

        Steps:
        1. Match extracted terms against library
        2. For matches: use library translations, mark library_term_id
        3. For non-matches: keep LLM suggestions as-is
        4. Supplement injection: scan remaining library terms against source_text
        5. Sort: library terms first, then new terms

        Returns a new Glossary with merged terms.
        """
        glossary = deepcopy(extracted_glossary)

        if not domain_ids:
            return glossary

        # Step 1-3: Match extracted terms against library (bidirectional)
        extracted_sources = [t.source for t in glossary.terms]
        library_matches = self._db.find_matching_terms_bidirectional(extracted_sources, domain_ids)

        matched_normalized: set[str] = set()
        library_terms: list[GlossaryTerm] = []
        new_terms: list[GlossaryTerm] = []
        touched_ids: list[int] = []

        for term in glossary.terms:
            normalized = term.source.strip().lower()
            lib_match = library_matches.get(normalized)

            if lib_match:
                matched_normalized.add(normalized)
                ai_targets = dict(term.targets) if term.targets else {}
                lib_targets = lib_match["targets"] or {}

                # Check if LLM suggested different translations for languages the library covers
                llm_differs = self._check_translation_differs(ai_targets, lib_targets)

                # Merge: AI fills missing languages, library wins where both exist
                term.library_term_id = lib_match["id"]
                term.targets = {**ai_targets, **lib_targets}
                term.strategy = lib_match["strategy"]
                term.confirmed = True
                # Recalculate frequency from source text for matched library terms
                if source_text:
                    term.frequency = self._count_term_frequency(term.source, source_text)

                if llm_differs:
                    term.uncertain = True
                    term.uncertainty_note = "TRANSLATION_DIFFERS"

                # Flag if target languages still missing after merge
                if target_languages:
                    missing = [l for l in target_languages if not term.targets.get(l)]
                    if missing:
                        term.uncertain = True
                        term.uncertainty_note = f"MISSING_TRANSLATIONS:{','.join(missing)}"

                touched_ids.append(lib_match["id"])
                library_terms.append(term)
            else:
                new_terms.append(term)

        # Step 4: Supplement injection
        if source_text:
            all_library_terms = self._db.get_all_terms_by_domains(domain_ids)
            injected = self._supplement_inject(
                all_library_terms,
                matched_normalized,
                source_text,
                glossary,
                target_languages=target_languages,
            )
            for inj_term in injected:
                touched_ids.append(inj_term.library_term_id)  # type: ignore[arg-type]
            library_terms.extend(injected)

        # Touch used terms
        if touched_ids:
            self._db.touch_terms(touched_ids)

        # Step 5: Sort — library terms first, then new terms
        glossary.terms = library_terms + new_terms

        # Re-number IDs
        for idx, term in enumerate(glossary.terms, start=1):
            term.id = f"term_{idx:03d}"

        lib_count = len(library_terms)
        new_count = len(new_terms)
        logger.info(
            "Merge complete: %d library terms, %d new terms", lib_count, new_count
        )

        return glossary

    def _supplement_inject(
        self,
        all_library_terms: list[dict],
        already_matched: set[str],
        source_text: str,
        glossary: Glossary,
        target_languages: list[str] | None = None,
    ) -> list[GlossaryTerm]:
        """Inject library terms that LLM missed but appear in source text."""
        injected: list[GlossaryTerm] = []

        # Track which source spans are already covered by longer terms
        # to avoid injecting "machine" when "machine learning" already matched
        covered_sources: set[str] = set(already_matched)

        for lib_term in all_library_terms:
            normalized = lib_term["source_normalized"]
            if normalized in covered_sources:
                continue

            # Check source and all target values against source_text
            source = lib_term["source"]
            found = self._term_appears_in_text(source, source_text)
            if not found:
                for val in lib_term.get("targets", {}).values():
                    if val and self._term_appears_in_text(val, source_text):
                        found = True
                        break
            if not found:
                continue

            # Check if this term is a substring of an already-covered longer term
            is_substring = any(
                normalized in covered and normalized != covered
                for covered in covered_sources
            )
            if is_substring:
                continue

            covered_sources.add(normalized)

            lib_targets = lib_term["targets"] or {}
            missing = [l for l in (target_languages or []) if not lib_targets.get(l)]

            # Compute frequency in source text
            freq = self._count_term_frequency(source, source_text)

            term = GlossaryTerm(
                source=source,
                targets=lib_targets,
                strategy=lib_term["strategy"],
                ai_category=lib_term.get("ai_category", ""),
                context=lib_term.get("context", ""),
                confirmed=not missing,
                library_term_id=lib_term["id"],
                uncertain=bool(missing),
                uncertainty_note=f"MISSING_TRANSLATIONS:{','.join(missing)}" if missing else "",
                frequency=freq,
            )
            injected.append(term)

        if injected:
            logger.info("Supplement injection: %d terms added from library", len(injected))

        return injected

    @staticmethod
    def _count_term_frequency(source: str, text: str) -> int:
        """Count occurrences of a term in text (case-insensitive)."""
        if not source or not text:
            return 0
        text_lower = text.lower()
        term_lower = source.lower()
        count = 0
        start = 0
        while True:
            pos = text_lower.find(term_lower, start)
            if pos == -1:
                break
            count += 1
            start = pos + len(term_lower)
        return count

    @staticmethod
    def _term_appears_in_text(source: str, text: str) -> bool:
        """Check if a term appears in text with appropriate boundary matching."""
        if not source or not text:
            return False

        # For terms that are purely ASCII (English terms, acronyms)
        if source.isascii():
            # Word boundary matching for English terms
            pattern = r"\b" + re.escape(source) + r"\b"
            return bool(re.search(pattern, text, re.IGNORECASE))

        # For CJK and mixed terms: direct substring match (case-insensitive)
        return source.lower() in text.lower()

    @staticmethod
    def _check_translation_differs(
        llm_targets: dict[str, str], lib_targets: dict[str, str]
    ) -> bool:
        """Check if LLM suggested different translations from library."""
        for lang, llm_val in llm_targets.items():
            if not llm_val:
                continue
            lib_val = lib_targets.get(lang, "")
            if lib_val and llm_val.strip() != lib_val.strip():
                return True
        return False

    # ── save-back ─────────────────────────────────────────────────

    # Map normalized document domain keys to stable DB domain name keys
    # Must match the `name` column in TermLibraryDB._DEFAULT_DOMAINS
    SUBJECT_DOMAIN_NAMES: dict[str, str] = {
        "economics_finance": "economics_finance",
        "law": "law",
        "medical": "medical",
        "information_technology": "information_technology",
        "engineering": "engineering",
        "natural_science": "natural_science",
        "agriculture": "agriculture",
        "energy_environment": "energy_environment",
        "education": "education",
        "politics_military": "politics_military",
        "social_science": "social_science",
        "literature_arts": "literature_arts",
        "media_communication": "media_communication",
        "business": "business",
        "general": "general",
    }

    def _get_or_create_domain(self, domain_name: str) -> int:
        """Find an existing domain by name, or create it."""
        domains = self._db.list_domains()
        for d in domains:
            if d["name"] == domain_name:
                return d["id"]
        domain_id = self._db.create_domain(domain_name, f"根据文档主题自动创建的领域：{domain_name}")
        logger.info("Auto-created subject domain '%s' (id=%d)", domain_name, domain_id)
        return domain_id

    def _resolve_domain_ids_for_save(
        self,
        user_selected_domain_ids: list[int],
        document_domains: list[str],
    ) -> list[int]:
        """Determine which subject-matter domain(s) to save new terms into.

        Priority:
        1. User explicitly selected domain(s) at upload time → use all of them
        2. No selection → auto-create/match based on LLM-detected document_domains
        """
        if user_selected_domain_ids:
            return user_selected_domain_ids

        from src.terminology.extractor import _normalize_document_domain

        domain_ids: list[int] = []
        for raw_domain in document_domains:
            normalized = _normalize_document_domain(raw_domain)
            domain_name = self.SUBJECT_DOMAIN_NAMES.get(normalized, "通用")
            domain_ids.append(self._get_or_create_domain(domain_name))

        return domain_ids or [self._get_or_create_domain("通用")]

    def save_confirmed_terms(
        self,
        glossary: Glossary,
        save_new_term_ids: set[str] | None = None,
        update_library_term_ids: set[str] | None = None,
        user_selected_domain_ids: list[int] | None = None,
        document_domains: list[str] | None = None,
    ) -> tuple[int, int]:
        """Save terms back to the library.

        New terms are placed into subject-matter domain(s) based on:
        1. User-selected domain(s) (if any), or
        2. LLM-detected document_domains (auto-created if needed).

        A term is saved into every target domain (supports cross-domain documents).
        Library terms are updated in-place (their domain doesn't change).

        Args:
            glossary: The confirmed glossary
            save_new_term_ids: IDs of new terms user marked "save to library"
            update_library_term_ids: IDs of library terms user chose to update
            user_selected_domain_ids: Domain IDs the user chose at upload time
            document_domains: LLM-detected document domains (fallback)

        Returns: (new_count, updated_count)
        """
        new_count = 0
        updated_count = 0

        # Resolve target domain(s) once for all new terms in this document
        target_domain_ids: list[int] | None = None

        for term in glossary.terms:
            if term.strategy == "skip":
                continue

            # New term: save if user marked it
            if term.library_term_id is None:
                if save_new_term_ids and term.id in save_new_term_ids:
                    if target_domain_ids is None:
                        target_domain_ids = self._resolve_domain_ids_for_save(
                            user_selected_domain_ids or [],
                            document_domains or ["general"],
                        )

                    # Enrich targets with source language
                    enriched_targets = dict(term.targets)
                    if glossary.source_language:
                        enriched_targets.setdefault(glossary.source_language, term.source)

                    for domain_id in target_domain_ids:
                        # Dedup: check if term already exists by any value
                        existing = self._db.find_term_by_any_value(term.source, domain_id)
                        if existing:
                            # Merge into existing entry
                            self._db.update_term(
                                existing["id"],
                                targets=enriched_targets,
                            )
                        else:
                            self._db.upsert_term(
                                domain_id=domain_id,
                                source=term.source,
                                targets=enriched_targets,
                                strategy=term.strategy,
                                ai_category=term.ai_category,
                                context=term.context,
                            )
                    new_count += 1

            # Library term: update if user modified and chose to sync
            elif update_library_term_ids and term.id in update_library_term_ids:
                update_targets = dict(term.targets)
                if glossary.source_language:
                    update_targets.setdefault(glossary.source_language, term.source)
                self._db.update_term(
                    term.library_term_id,
                    targets=update_targets,
                    strategy=term.strategy,
                    context=term.context,
                )
                updated_count += 1

            # Auto-accumulate: silently save new language translations back to library
            elif term.library_term_id is not None:
                current_targets = dict(term.targets)
                if glossary.source_language:
                    current_targets.setdefault(glossary.source_language, term.source)
                # Only save non-empty translations for the current job's target languages
                new_lang_targets = {
                    lang: val for lang, val in current_targets.items()
                    if val and lang in (glossary.target_languages or [])
                }
                if new_lang_targets:
                    self._db.update_term(
                        term.library_term_id,
                        targets=new_lang_targets,
                    )

        if new_count or updated_count:
            logger.info(
                "Library save-back: %d new, %d updated", new_count, updated_count
            )

        return new_count, updated_count

    # ── import / export ───────────────────────────────────────────

    def import_csv(
        self, domain_id: int, content: str, delimiter: str = ","
    ) -> tuple[int, int]:
        """Import terms from CSV/TSV content.

        Expected format:
            source,zh-CN,en,ja,...,strategy,context
        First column must be 'source'. Language columns auto-detected.
        'strategy' and 'context' are optional.
        """
        reader = csv.DictReader(io.StringIO(content), delimiter=delimiter)
        if not reader.fieldnames:
            return 0, 0

        fields = [f.strip().lower() for f in reader.fieldnames]
        if "source" not in fields:
            raise ValueError("CSV must have a 'source' column")

        # Build field mapping
        meta_fields = {"source", "strategy", "context", "category", "ai_category"}
        lang_fields = [f for f in fields if f not in meta_fields]

        terms: list[dict] = []
        for row in reader:
            # Normalize keys
            row = {k.strip().lower(): v.strip() for k, v in row.items() if v and v.strip()}
            source = row.get("source", "")
            if not source:
                continue

            targets = {}
            for lang in lang_fields:
                val = row.get(lang, "")
                if val:
                    # Restore original case from fieldnames
                    orig_key = next(
                        (f for f in reader.fieldnames if f.strip().lower() == lang),
                        lang,
                    )
                    targets[orig_key.strip()] = val

            terms.append({
                "source": source,
                "targets": targets,
                "strategy": row.get("strategy", "hard"),
                "ai_category": row.get("ai_category") or row.get("category", ""),
                "context": row.get("context", ""),
            })

        return self._db.bulk_upsert(domain_id, terms)

    def import_tsv(self, domain_id: int, content: str) -> tuple[int, int]:
        return self.import_csv(domain_id, content, delimiter="\t")

    def export_csv(self, domain_id: int) -> str:
        return self._export_delimited(domain_id, delimiter=",")

    def export_tsv(self, domain_id: int) -> str:
        return self._export_delimited(domain_id, delimiter="\t")

    def export_json(self, domain_id: int) -> str:
        terms = self._db.export_domain(domain_id)
        # Clean up internal fields for export
        for t in terms:
            for key in ("id", "domain_id", "source_normalized", "created_at", "updated_at", "last_used_at", "use_count"):
                t.pop(key, None)
        return json.dumps(terms, ensure_ascii=False, indent=2)

    def _export_delimited(self, domain_id: int, delimiter: str = ",") -> str:
        terms = self._db.export_domain(domain_id)
        if not terms:
            return ""

        # Collect all language keys across all terms
        all_langs: list[str] = []
        for t in terms:
            for lang in t.get("targets", {}):
                if lang not in all_langs:
                    all_langs.append(lang)

        output = io.StringIO()
        fieldnames = ["source"] + all_langs + ["strategy", "ai_category", "context"]
        writer = csv.DictWriter(output, fieldnames=fieldnames, delimiter=delimiter)
        writer.writeheader()

        for t in terms:
            row = {"source": t["source"]}
            targets = t.get("targets", {})
            for lang in all_langs:
                row[lang] = targets.get(lang, "")
            row["strategy"] = t.get("strategy", "hard")
            row["ai_category"] = t.get("ai_category", "")
            row["context"] = t.get("context", "")
            writer.writerow(row)

        return output.getvalue()
