"""Terminology Agent: extract terms and present glossary for translator review.

Terms start unconfirmed — the translator reviews and confirms them before
translation begins. No automatic filtering, expert review, or authority lookup.
"""

from __future__ import annotations

import json
import logging

from rich.console import Console
from rich.table import Table

from src.llm.poe_client import get_client
from src.models.glossary import Glossary, GlossaryTerm
from src.terminology.extractor import TerminologyExtractor
from src.terminology.glossary import GlossaryManager
from src.utils.glossary_export import build_glossary_table
from src.utils.language_detect import get_language_name

logger = logging.getLogger(__name__)
console = Console()


class TerminologyAgent:
    """Extract term candidates and present them for translator review."""

    def __init__(self) -> None:
        self._extractor = TerminologyExtractor()
        self._manager = GlossaryManager()

    async def run(
        self,
        text: str,
        source_language: str,
        target_languages: list[str],
        source_file: str = "",
        library_domain_ids: list[int] | None = None,
    ) -> Glossary:
        console.print("\n[bold cyan]▶ 正在提取术语候选…[/bold cyan]")
        terms, document_domains = await self._extractor.extract(text, source_language, target_languages)

        if terms:
            console.print(f"  提取到 {len(terms)} 个候选术语（待译员确认）")
        else:
            console.print("[yellow]  未提取到需要管理的术语。[/yellow]")

        terms.sort(key=lambda t: t.frequency, reverse=True)

        for idx, term in enumerate(terms, start=1):
            term.id = f"term_{idx:03d}"

        glossary = self._manager.create_from_terms(terms, source_language, target_languages)
        glossary.source_file = source_file
        glossary.document_domains = document_domains
        # NOTE: do NOT call confirm_all — terms start unconfirmed; translator confirms them

        # Merge with terminology library if domain_ids provided
        if library_domain_ids:
            from src.terminology.library_service import TermLibraryService

            service = TermLibraryService()
            glossary = service.merge_with_extracted(
                glossary, library_domain_ids, source_text=text,
                target_languages=target_languages,
            )
            lib_count = sum(1 for t in glossary.terms if t.library_term_id is not None)
            new_count = sum(1 for t in glossary.terms if t.library_term_id is None)
            console.print(
                f"  术语库合并：[green]{lib_count}[/green] 个来自术语库，"
                f"[yellow]{new_count}[/yellow] 个新提取"
            )

            # Fill missing target language translations via LLM
            gap_terms = [
                t for t in glossary.terms
                if t.strategy != "skip"
                and any(not t.targets.get(lang) for lang in target_languages)
            ]
            if gap_terms:
                console.print(
                    f"  [cyan]正在为 {len(gap_terms)} 个术语补全目标语言翻译…[/cyan]"
                )
                await self._fill_missing_translations(
                    gap_terms, source_language, target_languages
                )

        self._show_terms(glossary)
        return glossary

    # ── fill missing translations ───────────────────────────────────

    @staticmethod
    async def _fill_missing_translations(
        terms: list[GlossaryTerm],
        source_language: str,
        target_languages: list[str],
    ) -> None:
        """Call LLM to translate terms that are missing target language translations.

        Modifies terms in-place. Only fills languages that are empty.
        """
        # Build a compact request: [{source, missing_langs}]
        requests = []
        for term in terms:
            missing = [l for l in target_languages if not term.targets.get(l)]
            if missing:
                requests.append({
                    "source": term.source,
                    "context": term.context or "",
                    "missing_languages": missing,
                })

        if not requests:
            return

        prompt = (
            f"You are a terminology translator. Source language: {source_language}.\n"
            f"For each term below, provide translations for the specified missing languages.\n"
            f"Return a JSON array in the same order. Each element: "
            f'{{"source": "...", "translations": {{"lang_code": "translation", ...}}}}\n'
            f"Be precise and concise. Use standard terminology for the domain.\n"
            f"If the term is an acronym/abbreviation that is universally kept as-is "
            f"in the target language, return the original.\n\n"
            f"Terms:\n{json.dumps(requests, ensure_ascii=False)}"
        )

        try:
            client = get_client()
            raw = await client.simple_chat(
                user_message=prompt,
                temperature=0.2,
                model=client.get_model("terminology"),
            )

            # Parse response
            import re
            text = raw.strip()
            text = re.sub(r"^```(?:json)?\s*", "", text)
            text = re.sub(r"\s*```$", "", text)
            data = json.loads(text)

            if not isinstance(data, list):
                logger.warning("Fill translations: expected list, got %s", type(data).__name__)
                return

            # Map results back to terms
            source_map = {item["source"]: item.get("translations", {}) for item in data if isinstance(item, dict)}
            filled = 0
            for term in terms:
                translations = source_map.get(term.source, {})
                for lang, val in translations.items():
                    if val and not term.targets.get(lang):
                        term.targets[lang] = val
                        filled += 1
                # Clear uncertain flag if all target languages now have translations
                if term.uncertain and all(term.targets.get(l) for l in target_languages):
                    term.uncertain = False
                    term.uncertainty_note = ""

            logger.info("Filled %d missing translations for %d terms", filled, len(terms))
            console.print(f"  [green]已补全 {filled} 个缺失翻译[/green]")

        except Exception as e:
            logger.warning("Failed to fill missing translations: %s", e)
            console.print(f"  [yellow]补全翻译失败，请在审核时手动补充: {e}[/yellow]")

    # ── display ──────────────────────────────────────────────────────

    @staticmethod
    def _show_terms(glossary: Glossary) -> None:
        if not glossary.terms:
            console.print("[dim]（术语表为空）[/dim]")
            return

        src_lang_name = get_language_name(glossary.source_language) if glossary.source_language else "原文"
        languages = glossary.resolved_target_languages
        table_data = build_glossary_table(glossary)

        title = "术语候选（待确认）"
        if glossary.source_file:
            title = f"术语候选 — 来源：{glossary.source_file}"

        table = Table(title=title, show_lines=True)
        table.add_column("#", style="bold", justify="right", width=4)
        table.add_column(src_lang_name, style="cyan")
        for language in languages:
            table.add_column(
                get_language_name(language) if language else language,
                style="green",
            )
        table.add_column("类别", style="magenta")
        table.add_column("策略", style="blue")
        table.add_column("频次", style="yellow", justify="right")
        table.add_column("领域含义", style="dim italic", max_width=40)

        for idx, row in enumerate(table_data["rows"], start=1):
            language_values = [str(row.get(language, "")) for language in languages]
            source_display = str(row["source"])
            # Add uncertainty marker if applicable
            # We need to find the actual term to check uncertain flag
            term = next((t for t in glossary.terms if t.source == row["source"]), None)
            if term and term.uncertain:
                source_display = f"⚠ {source_display}"

            strategy = ""
            if term:
                strategy_map = {"hard": "刚性翻译", "keep_original": "保留原文", "skip": "跳过"}
                strategy = strategy_map.get(term.strategy, term.strategy)

            table.add_row(
                str(idx),
                source_display,
                *language_values,
                str(row.get("category") or row.get("ai_category") or ""),
                strategy,
                str(row.get("frequency") or "-"),
                str(row.get("context") or "-"),
            )
        console.print(table)
