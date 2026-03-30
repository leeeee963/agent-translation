from __future__ import annotations

import json
import logging
import re
from collections import Counter
from pathlib import Path

from src.llm.poe_client import get_client
from src.models.glossary import GlossaryTerm

logger = logging.getLogger(__name__)

# ── document domain normalization ─────────────────────────────────────

_VALID_DOCUMENT_DOMAINS = frozenset({
    "economics_finance", "law", "medical", "information_technology",
    "engineering", "natural_science", "agriculture", "energy_environment",
    "education", "politics_military", "social_science", "literature_arts",
    "media_communication", "business", "general",
})

# LLM may return synonyms / variants → canonical key (all lowercase match)
_DOMAIN_SYNONYMS: dict[str, str] = {
    # economics_finance
    "finance": "economics_finance", "economics": "economics_finance",
    "financial": "economics_finance", "banking": "economics_finance",
    "accounting": "economics_finance", "investment": "economics_finance",
    "insurance": "economics_finance", "economy": "economics_finance",
    "fiscal": "economics_finance", "trading": "economics_finance",
    "management": "economics_finance", "statistics": "economics_finance",
    # law
    "legal": "law", "judicial": "law", "regulatory": "law",
    "compliance": "law", "legislation": "law",
    # medical
    "healthcare": "medical", "health": "medical", "medicine": "medical",
    "clinical": "medical", "pharmaceutical": "medical", "biomedical": "medical",
    "pharmacy": "medical",
    # information_technology
    "technology": "information_technology", "tech": "information_technology",
    "it": "information_technology", "software": "information_technology",
    "computing": "information_technology", "digital": "information_technology",
    "ai": "information_technology", "cybersecurity": "information_technology",
    "blockchain": "information_technology", "computer": "information_technology",
    "telecommunications": "information_technology",
    # engineering
    "mechanical": "engineering", "civil": "engineering",
    "construction": "engineering", "manufacturing": "engineering",
    "automotive": "engineering", "aerospace": "engineering",
    "chemical_engineering": "engineering", "materials": "engineering",
    "transportation": "engineering",
    # natural_science
    "science": "natural_science", "physics": "natural_science",
    "chemistry": "natural_science", "biology": "natural_science",
    "mathematics": "natural_science", "astronomy": "natural_science",
    "geology": "natural_science",
    # agriculture
    "farming": "agriculture", "forestry": "agriculture",
    "fishery": "agriculture", "veterinary": "agriculture",
    # energy_environment
    "energy": "energy_environment", "environment": "energy_environment",
    "environmental": "energy_environment", "nuclear": "energy_environment",
    "ecology": "energy_environment", "climate": "energy_environment",
    # education
    "academic": "education", "teaching": "education",
    "training": "education", "sports": "education",
    # politics_military
    "politics": "politics_military", "political": "politics_military",
    "government": "politics_military", "military": "politics_military",
    "defense": "politics_military", "defence": "politics_military",
    "diplomacy": "politics_military", "policy": "politics_military",
    # social_science
    "philosophy": "social_science", "sociology": "social_science",
    "psychology": "social_science", "history": "social_science",
    "religion": "social_science", "anthropology": "social_science",
    "archaeology": "social_science",
    # literature_arts
    "literature": "literature_arts", "art": "literature_arts",
    "arts": "literature_arts", "linguistics": "literature_arts",
    "culture": "literature_arts", "music": "literature_arts",
    "film": "literature_arts",
    # media_communication
    "media": "media_communication", "journalism": "media_communication",
    "communication": "media_communication", "publishing": "media_communication",
    # business
    "marketing": "business", "advertising": "business", "branding": "business",
    "sales": "business", "pr": "business",
    "commerce": "business", "ecommerce": "business",
    "retail": "business",
    # general
    "entertainment": "general", "gaming": "general",
    "tourism": "general", "travel": "general",
}


def _normalize_document_domain(raw: str) -> str:
    """Normalize an LLM-returned document_domain to a canonical enum value."""
    if not raw:
        return "general"
    key = raw.strip().lower().replace(" ", "_").replace("-", "_")
    if key in _VALID_DOCUMENT_DOMAINS:
        return key
    if key in _DOMAIN_SYNONYMS:
        return _DOMAIN_SYNONYMS[key]
    logger.warning("Cannot map document_domain '%s' to known domain, using 'general'", raw)
    return "general"


# Languages whose scripts use CJK characters.
# Translations for any other language that contain CJK are wrong — clear them.
_CJK_LANGUAGES = {"zh-CN", "zh-TW", "zh", "ja", "ko"}


# ── acronym stop-list: common non-terminology abbreviations ──────────
# Includes universal abbreviations, 2-letter English words that happen to be
# all-caps in some contexts, and everyday short forms.
_ACRONYM_STOP_LIST = frozenset({
    # Common 2-letter English words (all-caps in transcripts)
    "AM", "AN", "AS", "AT", "BE", "BY", "DO", "GO", "HA", "HE", "IF",
    "IN", "IS", "IT", "ME", "MY", "NO", "OF", "OH", "OK", "ON", "OR",
    "OX", "SO", "TO", "UP", "US", "WE",
    # Universal abbreviations that never need translation guidance
    "AD", "BC", "EU", "HR", "ID", "PM", "PR", "QA", "TV", "UK", "UN",
    "VS", "CD", "DJ", "FM", "PC", "VR", "AR", "OP", "RE", "CC", "BCC",
    # Conversational fillers
    "GG", "LOL", "OMG", "WOW", "YEP", "NAH", "HMM", "UMM",
})


def _edit_distance(a: str, b: str) -> int:
    """Compute Levenshtein edit distance between two short strings."""
    if len(a) < len(b):
        return _edit_distance(b, a)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a):
        curr = [i + 1]
        for j, cb in enumerate(b):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (ca != cb)))
        prev = curr
    return prev[-1]


def _contains_cjk(text: str) -> bool:
    return any(
        "\u4e00" <= ch <= "\u9fff"
        or "\u3400" <= ch <= "\u4dbf"
        or "\uf900" <= ch <= "\ufaff"
        for ch in text
    )


def _clean_wrong_script_targets(terms: list[GlossaryTerm]) -> list[GlossaryTerm]:
    """Clear translations that contain CJK characters for non-CJK target languages."""
    for term in terms:
        if term.do_not_translate:
            continue
        for lang in list(term.targets.keys()):
            if lang not in _CJK_LANGUAGES and _contains_cjk(term.targets[lang]):
                logger.info(
                    "Cleared wrong-script translation for '%s' [%s]: '%s'",
                    term.source, lang, term.targets[lang],
                )
                term.targets[lang] = ""
    return terms

_VALID_AI_CATEGORIES = frozenset({
    "proper_noun", "person", "place", "brand", "domain_term", "ambiguous",
})

from src.utils.paths import get_config_dir

_PROMPT_PATH = get_config_dir() / "prompts" / "terminology.md"


class TerminologyExtractor:
    """Extract domain-specific terms from source text via LLM."""

    def __init__(self) -> None:
        self._prompt_template = self._load_prompt()

    @staticmethod
    def _load_prompt() -> str:
        if not _PROMPT_PATH.exists():
            raise FileNotFoundError(f"Prompt template not found: {_PROMPT_PATH}")
        return _PROMPT_PATH.read_text(encoding="utf-8")

    @staticmethod
    def _scan_acronyms(text: str) -> list[str]:
        """Scan text for meaningful all-caps acronyms, filtering noise.

        Applies three filters:
        1. Stop-list: removes common non-terminology abbreviations (US, OK, TV, etc.)
        2. Minimum frequency ≥2: removes single-occurrence ASR transcription errors
        3. ASR variant detection: if a low-frequency acronym is edit-distance ≤1 from
           a higher-frequency one, it's likely a transcription error — remove it.
        """
        caps = re.findall(r'\b[A-Z]{2,8}\b', text)
        counts = Counter(caps)

        # Filter: stop-list + minimum frequency
        candidates = [
            (term, cnt) for term, cnt in counts.most_common()
            if term not in _ACRONYM_STOP_LIST and cnt >= 2
        ]

        # Filter: ASR variant detection (edit distance ≤1 from a higher-freq term)
        kept: list[str] = []
        for term, cnt in candidates:
            is_asr_variant = False
            if len(term) <= 4:  # only check short acronyms for ASR confusion
                for other, other_cnt in candidates:
                    if other == term:
                        continue
                    if other_cnt > cnt and _edit_distance(term, other) <= 1:
                        logger.info(
                            "Skipping likely ASR variant '%s' (%d) — similar to '%s' (%d)",
                            term, cnt, other, other_cnt,
                        )
                        is_asr_variant = True
                        break
            if not is_asr_variant:
                kept.append(term)

        return kept

    async def extract(
        self,
        text: str,
        source_language: str,
        target_languages: list[str],
    ) -> tuple[list[GlossaryTerm], list[str]]:
        """Extract terms and detect document domains.

        Returns: (terms, document_domains)
        """
        # Always reload from disk so prompt edits take effect without server restart
        system_message = self._load_prompt()

        acronyms = self._scan_acronyms(text)
        acronym_hint = ""
        if acronyms:
            acronym_hint = (
                f"\n\nThe following acronyms appear multiple times in the text. "
                f"Evaluate each one — extract it ONLY if it is a domain-specific "
                f"term that a translator genuinely needs guidance on. "
                f"Skip common/generic ones per your instructions:\n"
                + ", ".join(acronyms)
            )

        user_message = (
            f"Source language: {source_language}\n"
            f"Target languages: {', '.join(target_languages)}\n\n"
            f"Text:\n{text}"
            f"{acronym_hint}"
        )

        client = get_client()
        raw = await client.simple_chat(
            user_message=user_message,
            system_message=system_message,
            temperature=0.3,
            model=client.get_model("terminology"),
        )

        terms, document_domains = self._parse_response(raw)
        # Clear any LLM-set uncertain flags — uncertain is only set by library merge logic
        for t in terms:
            t.uncertain = False
            t.uncertainty_note = ""
        # Diagnostic: log what the LLM returned for each term's targets
        for t in terms[:5]:  # first 5 terms
            logger.info("LLM term '%s' targets: %s strategy: %s", t.source, t.targets, t.strategy)
        logger.info("Detected document_domains: %s", document_domains)
        text_lower = text.lower()
        for idx, term in enumerate(terms, start=1):
            term.id = f"term_{idx:03d}"
            term.frequency = self._count_occurrences(text_lower, term.source.lower())

        # Remove terms that don't appear in the source text — these are LLM hallucinations.
        before = len(terms)
        terms = [t for t in terms if t.frequency > 0]
        removed = before - len(terms)
        if removed:
            logger.info("Removed %d hallucinated term(s) with frequency=0", removed)

        # Clear translations that use the wrong script (e.g. Chinese characters in Mongolian).
        terms = _clean_wrong_script_targets(terms)

        # Backfill any empty target slots with the source term.
        # Covers low-resource languages (e.g. Mongolian, Kazakh) where the LLM returns "".
        # For keep_original terms: source is the intended final value anyway.
        # For hard terms: source gives the translator a starting point to edit from.
        # Skip: don't backfill skipped terms.
        for term in terms:
            if term.strategy == "skip":
                continue
            for lang in target_languages:
                if not term.targets.get(lang):
                    term.targets[lang] = term.source

        # ── Quality filters ──────────────────────────────────────────
        # 1. Remove keep_original terms where source == target in ALL languages
        #    (no translation decision needed — these waste translator's time)
        before = len(terms)
        def _has_translation_value(term: GlossaryTerm) -> bool:
            if term.strategy != "keep_original":
                return True
            src = term.source.strip().lower()
            return any(
                t.strip().lower() != src
                for t in term.targets.values()
                if t
            )
        terms = [t for t in terms if _has_translation_value(t)]
        removed_notranslation = before - len(terms)
        if removed_notranslation:
            logger.info(
                "Removed %d keep_original term(s) where source=target in all languages",
                removed_notranslation,
            )

        # 2. ASR variant dedup: among short all-caps terms (≤4 chars),
        #    if two terms are edit-distance ≤1 apart, keep the higher-frequency one.
        acronym_terms = [t for t in terms if len(t.source) <= 4 and t.source.isupper()]
        to_remove_ids: set[str] = set()
        for i, a in enumerate(acronym_terms):
            if a.id in to_remove_ids:
                continue
            for b in acronym_terms[i + 1:]:
                if b.id in to_remove_ids:
                    continue
                if _edit_distance(a.source, b.source) <= 1:
                    victim = b if a.frequency >= b.frequency else a
                    winner = a if victim is b else b
                    to_remove_ids.add(victim.id)
                    logger.info(
                        "ASR dedup: removed '%s' (freq=%d), kept '%s' (freq=%d)",
                        victim.source, victim.frequency, winner.source, winner.frequency,
                    )
        if to_remove_ids:
            terms = [t for t in terms if t.id not in to_remove_ids]

        return terms, document_domains

    @staticmethod
    def _count_occurrences(text_lower: str, term_lower: str) -> int:
        if not term_lower:
            return 0
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
    def _parse_response(raw: str) -> tuple[list[GlossaryTerm], list[str]]:
        """Best-effort parse of LLM JSON output into GlossaryTerm list + document_domains.

        Handles three formats:
        - New format: {"document_domains": [...], "terms": [...]}
        - Transition format: {"document_domain": "...", "terms": [...]}  (single value → list)
        - Old format (backward compat): bare JSON array [...]  → ["general"]

        Returns: (terms, document_domains)
        """
        text = raw.strip()

        # Strip markdown code fences if present
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        text = text.strip()

        document_domains: list[str] = ["general"]

        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            # Try to locate a JSON object or array inside the response
            match = re.search(r"[\[{].*[}\]]", text, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group())
                except json.JSONDecodeError:
                    logger.warning("Failed to parse LLM response as JSON:\n%s", text[:500])
                    return [], document_domains
            else:
                logger.warning("No JSON found in LLM response:\n%s", text[:500])
                return [], document_domains

        # Dict format: {"document_domains": [...], "terms": [...]} or {"document_domain": "...", "terms": [...]}
        if isinstance(data, dict) and "terms" in data:
            # Prefer document_domains (list), fall back to document_domain (single value)
            raw_domains = data.get("document_domains")
            if isinstance(raw_domains, list) and raw_domains:
                document_domains = [_normalize_document_domain(d) for d in raw_domains if d]
            else:
                raw_domain = data.get("document_domain", "general") or "general"
                document_domains = [_normalize_document_domain(raw_domain)]
            if not document_domains:
                document_domains = ["general"]

            term_list = data["terms"]
            if not isinstance(term_list, list):
                logger.warning("Expected 'terms' to be a list, got %s", type(term_list).__name__)
                return [], document_domains
        elif isinstance(data, list):
            # Old format: bare JSON array (backward compat)
            term_list = data
        else:
            logger.warning("Unexpected JSON structure: %s", type(data).__name__)
            return [], document_domains

        terms: list[GlossaryTerm] = []
        for item in term_list:
            if not isinstance(item, dict):
                continue
            try:
                # Map suggested_strategy → strategy (new LLM output format)
                item = dict(item)
                if "suggested_strategy" in item and "strategy" not in item:
                    item["strategy"] = item.pop("suggested_strategy")
                elif "suggested_strategy" in item:
                    item.pop("suggested_strategy")
                # Validate ai_category — LLM occasionally puts domain names here
                if item.get("ai_category") and item["ai_category"] not in _VALID_AI_CATEGORIES:
                    logger.info(
                        "Invalid ai_category '%s' for term '%s', falling back to 'domain_term'",
                        item["ai_category"], item.get("source", "?"),
                    )
                    item["ai_category"] = "domain_term"
                terms.append(GlossaryTerm(**item))
            except Exception:
                logger.debug("Skipping malformed term entry: %s", item)
        return terms, document_domains
