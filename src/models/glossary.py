from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field


class GlossaryTerm(BaseModel):
    id: str = ""
    source: str
    targets: dict[str, str] = Field(default_factory=dict)
    category: str = ""
    context: str = ""
    do_not_translate: bool = False
    confirmed: bool = False
    frequency: int = 0
    # New strategy fields (added in terminology redesign)
    strategy: str = "hard"          # "hard" | "keep_original" | "skip"
    ai_category: str = ""           # "proper_noun" | "domain_term" | "ambiguous" | "person" | "place" | "brand"
    uncertain: bool = False         # AI is not confident about this term
    uncertainty_note: str = ""      # e.g. "no confirmed official Chinese name found"
    # Terminology library fields
    library_term_id: Optional[int] = None   # links back to library_terms.id (None = new term)
    save_to_library: bool = False            # user toggle: save this new term to library

    @property
    def target(self) -> str:
        if self.do_not_translate:
            return self.source
        for value in self.targets.values():
            if value:
                return value
        return ""

    def get_target(self, target_language: str | None = None) -> str:
        if self.do_not_translate:
            return self.source
        if not self.targets:
            return ""
        if not target_language:
            return self.target

        # Exact match — return even if empty (prevents cross-language fallback)
        if target_language in self.targets:
            return self.targets[target_language]

        # Case-insensitive match among keys not already checked
        target_lower = target_language.lower()
        for lang_code, value in self.targets.items():
            if lang_code.lower() == target_lower and value:
                return value

        # Base-language fallback only within the same script family
        # (e.g. zh-TW falls back to zh-CN, but mn never falls back to zh-CN)
        base = target_lower.split("-")[0]
        for lang_code, value in self.targets.items():
            if lang_code.lower().split("-")[0] == base and value:
                return value

        return ""

    def set_target(self, target_language: str, value: str) -> None:
        if not target_language:
            return
        self.targets[target_language] = value


class Glossary(BaseModel):
    glossary_id: str = ""
    source_language: str = ""
    target_languages: list[str] = Field(default_factory=list)
    source_file: str = ""
    document_domains: list[str] = Field(default_factory=lambda: ["general"])  # 文档主题领域（1~2个）
    terms: list[GlossaryTerm] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    confirmed: bool = False

    @property
    def target_language(self) -> str:
        return self.target_languages[0] if self.target_languages else ""

    @property
    def confirmed_terms(self) -> list[GlossaryTerm]:
        return [t for t in self.terms if t.confirmed]

    @property
    def resolved_target_languages(self) -> list[str]:
        if self.target_languages:
            return self.target_languages

        ordered: list[str] = []
        for term in self.terms:
            for target_language in term.targets:
                if target_language and target_language not in ordered:
                    ordered.append(target_language)
        return ordered

    def to_constraint_text(
        self,
        target_language: str | None = None,
        first_use_terms: set[str] | None = None,
        enable_bilingual_first_use: bool = False,
    ) -> str:
        """Format the glossary as a constraint block for injection into prompts.

        Only confirmed terms are included. Strategy determines the constraint type:
        - "hard": must use the specified translation
        - "keep_original": must keep source text unchanged
        - "skip": excluded from constraints
        """
        if not self.terms:
            return ""

        resolved_language = target_language or self.target_language or None
        first_use_terms = {term.lower() for term in (first_use_terms or set())}
        lines: list[str] = []
        for term in self.terms:
            # Only include confirmed terms
            if not term.confirmed:
                continue

            # Determine effective strategy (do_not_translate is backward compat for "keep_original")
            effective_strategy = term.strategy
            if effective_strategy == "hard" and term.do_not_translate:
                effective_strategy = "keep_original"

            if effective_strategy == "skip":
                continue

            if effective_strategy == "keep_original":
                lines.append(
                    f'- "{term.source}" -> keep unchanged, do not translate'
                    + (f" ({term.context})" if term.context else "")
                )
                continue

            # strategy == "hard"
            resolved_target = term.get_target(resolved_language)
            if not resolved_target:
                continue

            use_bilingual = (
                enable_bilingual_first_use and term.source.lower() in first_use_terms
            )
            rule = (
                f'must use "{resolved_target}" and on the first occurrence in this segment use "{resolved_target} ({term.source})"'
                if use_bilingual
                else f'must use "{resolved_target}"'
            )
            lines.append(
                f'- "{term.source}" -> {rule}'
                + (f" ({term.context})" if term.context else "")
            )

        # Build soft preferences from unconfirmed hard-strategy terms
        soft_lines: list[str] = []
        for term in self.terms:
            if term.confirmed:
                continue
            if term.strategy != "hard":
                continue
            resolved_target = term.get_target(resolved_language)
            if not resolved_target or resolved_target == term.source:
                continue
            soft_lines.append(
                f'- "{term.source}" -> prefer "{resolved_target}"'
                + (f" ({term.context})" if term.context else "")
            )

        if not lines and not soft_lines:
            return ""

        parts: list[str] = []

        if lines:
            header = (
                "Terminology constraints (must follow exactly):\n"
                + (
                    "When a term is marked for first-use annotation in this segment, render its first occurrence as target term followed by the source term in parentheses.\n"
                    if enable_bilingual_first_use
                    else "Use the prescribed term directly.\n"
                )
            )
            parts.append(header + "\n".join(lines))

        if soft_lines:
            parts.append(
                "Terminology preferences (apply for consistency; override only if context requires a different meaning):\n"
                + "\n".join(soft_lines)
            )

        return "\n\n".join(parts)
