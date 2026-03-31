"""Translator Agent: segment-aware translation driven by a unified prompt."""

from __future__ import annotations

import asyncio
import logging
import re
from pathlib import Path
from typing import Any, Callable

import yaml

from src.llm.poe_client import get_client
from src.models.content import BlockType, ContentBlock, ParsedFile
from src.models.glossary import Glossary
from src.prompt.version_manager import PromptVersionManager
from src.translator.merger import Merger
from src.translator.segmenter import Segmenter
from src.utils.language_detect import LANGUAGE_NAMES_EN
from src.utils.language_loader import get_structural_notes

logger = logging.getLogger(__name__)

from src.utils.paths import get_config_dir

_CONFIG_DIR = get_config_dir()
_PROMPT_PATH = _CONFIG_DIR / "prompts" / "translator_unified.md"
_REVIEW_PROMPT_PATH = _CONFIG_DIR / "prompts" / "naturalness_review.md"
_SETTINGS_PATH = _CONFIG_DIR / "settings.yaml"

_BLOCK_MARKER = "[[BLOCK:{block_id}]]"
_BLOCK_MARKER_RE = re.compile(r"\[\[BLOCK:([\w\-]+)\]\]")

ProgressCallback = Callable[[dict[str, Any]], None]


def _load_prompt_template() -> str:
    return _PROMPT_PATH.read_text(encoding="utf-8")


def _load_review_template() -> str:
    return _REVIEW_PROMPT_PATH.read_text(encoding="utf-8")


def _build_marked_review_input(blocks: list[ContentBlock]) -> str:
    """Build marked input for the review pass using translated text."""
    parts: list[str] = []
    for block in blocks:
        text = block.translated_text or block.source_text
        parts.append(f"{_BLOCK_MARKER.format(block_id=block.id)}\n{text}")
    return "\n\n".join(parts)


def _load_translation_settings() -> dict[str, Any]:
    try:
        with open(_SETTINGS_PATH, encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}
        return settings.get("translation", {})
    except Exception:
        return {}


def _build_marked_input(blocks: list[ContentBlock]) -> str:
    parts: list[str] = []
    for block in blocks:
        parts.append(f"{_BLOCK_MARKER.format(block_id=block.id)}\n{block.source_text}")
    return "\n\n".join(parts)


def _parse_marked_response(response: str, blocks: list[ContentBlock]) -> set[str]:
    """Parse marked response and return matched block ids."""
    block_map = {block.id: block for block in blocks}
    chunks = _BLOCK_MARKER_RE.split(response)
    matched_ids: set[str] = set()

    idx = 1
    while idx + 1 < len(chunks):
        block_id = chunks[idx].strip()
        text = chunks[idx + 1].strip()
        if block_id in block_map and text:
            block_map[block_id].translated_text = text
            matched_ids.add(block_id)
        idx += 2

    if matched_ids == set(block_map):
        return matched_ids

    logger.warning(
        "Marker-based parsing matched %d/%d blocks",
        len(matched_ids),
        len(blocks),
    )
    if not matched_ids:
        _fallback_split(response, blocks)
        return {block.id for block in blocks if block.translated_text}

    return matched_ids


def _fallback_split(response: str, blocks: list[ContentBlock]) -> None:
    if len(blocks) == 1:
        blocks[0].translated_text = response.strip()
        return

    paragraphs: list[str] = []
    current: list[str] = []
    for line in response.strip().splitlines():
        if line.strip():
            current.append(line)
            continue
        if current:
            paragraphs.append("\n".join(current))
            current = []
    if current:
        paragraphs.append("\n".join(current))

    if len(paragraphs) == len(blocks):
        for block, paragraph in zip(blocks, paragraphs):
            block.translated_text = paragraph.strip()
        return

    response_lines = response.strip().splitlines()
    source_lines = [max(1, len(block.source_text.strip().splitlines())) for block in blocks]
    total = sum(source_lines)
    line_idx = 0
    for idx, block in enumerate(blocks):
        take = max(1, round(source_lines[idx] / total * len(response_lines)))
        block.translated_text = "\n".join(response_lines[line_idx : line_idx + take]).strip()
        line_idx += take
    if line_idx < len(response_lines):
        tail = "\n".join(response_lines[line_idx:]).strip()
        if tail:
            blocks[-1].translated_text = (blocks[-1].translated_text + "\n" + tail).strip()


def _segment_translation_text(blocks: list[ContentBlock]) -> str:
    return "\n".join(
        block.translated_text.strip()
        for block in blocks
        if block.translated_text.strip()
    )


def _update_summary(
    current_summary: str,
    translated_segment: str,
    context_window_size: int,
) -> str:
    if not translated_segment:
        return current_summary[-context_window_size:]

    merged = (current_summary + "\n" + translated_segment).strip()
    return merged[-context_window_size:]


def _build_first_use_map(
    segments: list[list[ContentBlock]],
    glossary: Glossary,
) -> dict[int, set[str]]:
    """Map segment index to terms whose first document occurrence is inside it."""
    first_use_map: dict[int, set[str]] = {}
    seen_terms: set[str] = set()

    for idx, segment in enumerate(segments):
        segment_text = "\n".join(block.source_text.lower() for block in segment)
        for term in glossary.terms:
            key = term.source.lower()
            if key in seen_terms:
                continue
            if key in segment_text:
                first_use_map.setdefault(idx, set()).add(term.source)
                seen_terms.add(key)
    return first_use_map


def _unit_label_for_file(file_type: str) -> str:
    normalized = file_type.lower()
    if normalized == "pptx":
        return "slide"
    if normalized in {"srt", "vtt", "ass"}:
        return "subtitle"
    if normalized in {"docx", "doc"}:
        return "paragraph"
    return "block"


def _build_unit_map(parsed_file: ParsedFile) -> tuple[dict[str, int], int, str]:
    file_type = parsed_file.meta.file_type.lower()
    unit_label = _unit_label_for_file(file_type)
    block_to_unit: dict[str, int] = {}
    next_unit = 1

    for index, block in enumerate(parsed_file.translatable_blocks, start=1):
        unit_number: int | None = None
        if file_type == "pptx":
            slide_index = block.metadata.get("slide_index")
            if slide_index is not None:
                unit_number = int(slide_index) + 1
        elif file_type in {"srt", "vtt", "ass"}:
            subtitle_index = block.metadata.get("index")
            if subtitle_index is not None:
                unit_number = int(subtitle_index)
        elif file_type in {"docx", "doc"}:
            unit_number = index

        if unit_number is None:
            unit_number = next_unit
        next_unit = max(next_unit, unit_number + 1)
        block_to_unit[block.id] = unit_number

    total_units = len({value for value in block_to_unit.values()})
    return block_to_unit, total_units, unit_label


def _segment_range_label(
    segment: list[ContentBlock],
    block_to_unit: dict[str, int],
) -> str:
    values = sorted({block_to_unit.get(block.id) for block in segment if block.id in block_to_unit})
    values = [value for value in values if value is not None]
    if not values:
        return ""
    if len(values) == 1:
        return str(values[0])
    return f"{values[0]}-{values[-1]}"


def _count_units_done(
    completed_segments: list[list[ContentBlock]],
    block_to_unit: dict[str, int],
) -> int:
    return len(
        {
            block_to_unit[block.id]
            for segment in completed_segments
            for block in segment
            if block.id in block_to_unit
        }
    )


def _normalize_bilingual_terms(
    blocks: list[ContentBlock],
    glossary: Glossary,
    target_language: str,
) -> None:
    """Keep bilingual first-use annotation only once per term across the document."""
    seen_terms: set[str] = set()

    for term in glossary.terms:
        if term.do_not_translate:
            continue

        target = term.get_target(target_language)
        if not target:
            continue

        source = re.escape(term.source)
        target_pattern = re.escape(target)
        pattern = re.compile(
            rf"{target_pattern}\s*(?:\(|（)\s*{source}\s*(?:\)|）)",
            re.IGNORECASE,
        )
        term_key = term.source.lower()

        for block in blocks:
            text = block.translated_text or ""
            if not text:
                continue

            if term_key not in seen_terms:
                match = pattern.search(text)
                if match:
                    seen_terms.add(term_key)
                    first_match_end = match.end()
                    suffix = pattern.sub(target, text[first_match_end:])
                    block.translated_text = text[:first_match_end] + suffix
                continue

            if pattern.search(text):
                block.translated_text = pattern.sub(target, text)


class TranslatorAgent:
    """Segment-aware translation with glossary constraints and controlled concurrency."""

    def __init__(self) -> None:
        self._client = get_client()
        self._segmenter = Segmenter()
        self._merger = Merger()
        self._version_manager = PromptVersionManager()

    async def translate(
        self,
        parsed_file: ParsedFile,
        glossary: Glossary,
        target_language: str,
        source_language: str,
        progress_callback: ProgressCallback | None = None,
    ) -> ParsedFile:
        template = _load_prompt_template()
        settings = _load_translation_settings()

        self._version_manager.record(
            "translator_unified",
            template,
            notes=f"target={target_language}",
        )

        translatable = parsed_file.translatable_blocks
        if not translatable:
            logger.info("No translatable blocks found — skipping translation.")
            return parsed_file

        file_type = parsed_file.meta.file_type.lower()
        segment_token_limits = settings.get("segment_token_limits", {})
        max_tokens = int(
            segment_token_limits.get(
                file_type,
                segment_token_limits.get(
                    "subtitle" if translatable[0].type.value == "subtitle" else "default",
                    settings.get("max_segment_tokens", 2600),
                ),
            )
        )
        context_window_size = int(settings.get("context_window_size", 500))
        next_preview_chars = int(settings.get("next_preview_chars", 350))
        temperature = float(settings.get("temperature", {}).get("translation", 0.25))
        segment_options = settings.get("segmenting", {})

        segments = self._segmenter.segment(
            translatable,
            file_type=file_type,
            max_tokens=max_tokens,
            options=segment_options,
        )
        total_segments = len(segments)
        block_to_unit, total_units, unit_label = _build_unit_map(parsed_file)
        first_use_map = _build_first_use_map(segments, glossary)
        previous_summary = ""

        max_concurrent = self._resolve_concurrency(file_type, settings)
        window_size = max(1, min(max_concurrent, total_segments))

        if progress_callback:
            progress_callback(
                {
                    "segments_done": 0,
                    "segments_total": total_segments,
                    "units_done": 0,
                    "units_total": total_units,
                    "unit_label": unit_label,
                    "current_range": "",
                }
            )

        for window_start in range(0, total_segments, window_size):
            window_segments = segments[window_start : window_start + window_size]
            sem = asyncio.Semaphore(max(1, min(max_concurrent, len(window_segments))))

            segments_done_in_window = 0

            async def _run_in_window(offset: int, segment: list[ContentBlock]) -> None:
                nonlocal segments_done_in_window
                async with sem:
                    abs_idx = window_start + offset
                    logger.info(
                        "Translating segment %d/%d (%d blocks)",
                        abs_idx + 1,
                        total_segments,
                        len(segment),
                    )
                    await self._translate_segment(
                        segment=segment,
                        abs_idx=abs_idx,
                        segments=segments,
                        source_language=source_language,
                        source_language_name=LANGUAGE_NAMES_EN.get(source_language.lower(), source_language),
                        target_language=target_language,
                        target_language_name=LANGUAGE_NAMES_EN.get(target_language.lower(), target_language),
                        template=template,
                        glossary_constraints=glossary.to_constraint_text(
                            target_language=target_language,
                            first_use_terms=first_use_map.get(abs_idx, set()),
                            enable_bilingual_first_use=True,
                        ),
                        previous_summary=previous_summary,
                        context_window_size=context_window_size,
                        next_preview_chars=next_preview_chars,
                        temperature=temperature,
                    )
                    segments_done_in_window += 1
                    done_so_far = window_start + segments_done_in_window
                    if progress_callback:
                        progress_callback(
                            {
                                "segments_done": done_so_far,
                                "segments_total": total_segments,
                                "units_done": _count_units_done(
                                    segments[:done_so_far], block_to_unit
                                ),
                                "units_total": total_units,
                                "unit_label": unit_label,
                                "current_range": _segment_range_label(
                                    segment, block_to_unit,
                                ),
                            }
                        )

            await asyncio.gather(
                *[
                    _run_in_window(offset, segment)
                    for offset, segment in enumerate(window_segments)
                ]
            )

            for segment in window_segments:
                previous_summary = _update_summary(
                    previous_summary,
                    _segment_translation_text(segment),
                    context_window_size,
                )

        review_settings = settings.get("naturalness_review", {})
        if self._review_enabled(review_settings, target_language):
            review_template = _load_review_template()
            review_temperature = float(settings.get("temperature", {}).get("review", 0.3))
            review_total = len(segments)
            review_done = 0
            if progress_callback:
                progress_callback(
                    {
                        "status": "reviewing",
                        "segments_done": 0,
                        "segments_total": review_total,
                        "units_done": total_units,
                        "units_total": total_units,
                        "unit_label": unit_label,
                        "current_range": "",
                    }
                )

            async def _tracked_review(segment):
                nonlocal review_done
                result = await self._naturalize_segment(
                    segment=segment,
                    source_language_name=LANGUAGE_NAMES_EN.get(source_language.lower(), source_language),
                    target_language_name=LANGUAGE_NAMES_EN.get(target_language.lower(), target_language),
                    template=review_template,
                    language_structural_notes=get_structural_notes(target_language),
                    temperature=review_temperature,
                )
                review_done += 1
                if progress_callback:
                    progress_callback(
                        {
                            "status": "reviewing",
                            "segments_done": review_done,
                            "segments_total": review_total,
                            "units_done": total_units,
                            "units_total": total_units,
                            "unit_label": unit_label,
                            "current_range": "",
                        }
                    )
                return result

            results = await asyncio.gather(*[_tracked_review(seg) for seg in segments])
            all_changes = [change for result in results for change in result]
            logger.info(
                "Naturalness review complete for '%s': %d blocks rewritten",
                target_language,
                len(all_changes),
            )
            if progress_callback:
                progress_callback(
                    {
                        "status": "review_complete",
                        "review_changes": all_changes,
                    }
                )

        self._merger.merge(segments, parsed_file.blocks)
        _normalize_bilingual_terms(parsed_file.translatable_blocks, glossary, target_language)
        warnings = self._check_segment_integrity(
            parsed_file.translatable_blocks,
            glossary,
            target_language,
        )
        for warning in warnings:
            logger.warning("Post-translation issue: %s", warning)

        logger.info(
            "Translation complete: %d segments for '%s'",
            total_segments,
            parsed_file.meta.original_name,
        )
        return parsed_file

    @staticmethod
    def _review_enabled(review_settings: dict[str, Any], target_language: str) -> bool:
        if not review_settings.get("enabled", False):
            return False
        enabled_languages = review_settings.get("enabled_languages")
        if enabled_languages is None:
            return True
        return target_language.lower() in [lang.lower() for lang in enabled_languages]

    async def _naturalize_segment(
        self,
        *,
        segment: list[ContentBlock],
        source_language_name: str,
        target_language_name: str,
        template: str,
        language_structural_notes: str,
        temperature: float,
    ) -> list[dict]:
        """Run a naturalness review pass over an already-translated segment.

        Returns a list of change records for blocks whose translated_text was rewritten.
        """
        translated_blocks = [b for b in segment if b.translated_text]
        if not translated_blocks:
            return []

        originals = {b.id: b.translated_text for b in translated_blocks}

        system_message = template.format(
            source_language_name=source_language_name,
            target_language_name=target_language_name,
            language_structural_notes=language_structural_notes or "",
        )
        user_message = _build_marked_review_input(translated_blocks)

        response = await self._client.simple_chat(
            user_message=user_message,
            system_message=system_message,
            temperature=temperature,
            model=self._client.get_model("review"),
        )
        matched_ids = _parse_marked_response(response, translated_blocks)
        if len(matched_ids) < len(translated_blocks):
            logger.warning(
                "Naturalness review matched %d/%d blocks — keeping original translations for unmatched blocks",
                len(matched_ids),
                len(translated_blocks),
            )

        # Move reviewed text to reviewed_text; restore translated_text to pre-review original.
        # This lets parsers rebuild either version independently via _best_text().
        changes = []
        for b in translated_blocks:
            reviewed = b.translated_text
            original = originals.get(b.id, "")
            is_changed = reviewed != original
            if is_changed:
                b.reviewed_text = reviewed
                b.translated_text = original
            entry: dict = {
                "block_id": b.id,
                "changed": is_changed,
                "after": reviewed,
            }
            if is_changed:
                entry["source_text"] = b.source_text
                entry["before"] = original
            else:
                entry["source_text"] = ""
                entry["before"] = ""
            changes.append(entry)
        return changes

    @staticmethod
    def _resolve_concurrency(file_type: str, settings: dict[str, Any]) -> int:
        per_file = settings.get("max_concurrent_by_file_type", {})
        configured = int(per_file.get(file_type, settings.get("max_concurrent_requests", 3)))
        return max(1, configured)

    async def _translate_segment(
        self,
        *,
        segment: list[ContentBlock],
        abs_idx: int,
        segments: list[list[ContentBlock]],
        source_language: str,
        source_language_name: str,
        target_language: str,
        target_language_name: str,
        template: str,
        glossary_constraints: str,
        previous_summary: str,
        context_window_size: int,
        next_preview_chars: int,
        temperature: float,
    ) -> None:
        context = self._segmenter.build_context_hints(
            segments,
            abs_idx,
            previous_summary,
            context_window_size=context_window_size,
            preview_chars=next_preview_chars,
        )
        context_hint = context["combined"]
        user_msg = _build_marked_input(segment)

        for attempt in range(2):
            response = await self._client.simple_chat(
                user_message=user_msg,
                system_message=template.format(
                    source_language=source_language,
                    source_language_name=source_language_name,
                    target_language=target_language,
                    target_language_name=target_language_name,
                    glossary_constraints=glossary_constraints or "No terminology constraints.",
                    context_hint=context_hint or "None.",
                )
                + (
                    "\n\nERROR: Your previous response was missing one or more [[BLOCK:id]] markers. "
                    "Return ALL blocks. Every [[BLOCK:id]] marker must appear exactly once in your output."
                    if attempt == 1
                    else ""
                ),
                temperature=temperature,
                model=self._client.get_model("translation"),
            )
            matched_ids = _parse_marked_response(response, segment)
            if len(matched_ids) == len(segment):
                return
            for block in segment:
                if block.id not in matched_ids:
                    block.translated_text = ""

        if len(segment) == 1:
            raise RuntimeError(f"Segment translation failed for block {segment[0].id}")

        logger.warning(
            "Retrying segment %d as single-block translations (%d blocks)",
            abs_idx + 1,
            len(segment),
        )
        for block in segment:
            await self._translate_segment(
                segment=[block],
                abs_idx=abs_idx,
                segments=segments,
                source_language=source_language,
                source_language_name=source_language_name,
                target_language=target_language,
                target_language_name=target_language_name,
                template=template,
                glossary_constraints=glossary_constraints,
                previous_summary=previous_summary,
                context_window_size=context_window_size,
                next_preview_chars=next_preview_chars,
                temperature=temperature,
            )

    @staticmethod
    def _check_segment_integrity(
        blocks: list[ContentBlock],
        glossary: Glossary,
        target_language: str,
    ) -> list[str]:
        warnings: list[str] = []

        for block in blocks:
            if not (block.translated_text or "").strip():
                warnings.append(f"[{block.id}] translated text is empty")

        for term in glossary.terms:
            expected = term.get_target(target_language)
            if term.do_not_translate:
                expected = term.source
            if not expected:
                continue

            for block in blocks:
                translated = block.translated_text or ""
                if (
                    term.source.lower() in block.source_text.lower()
                    and expected.lower() not in translated.lower()
                ):
                    warnings.append(
                        f"[{block.id}] expected glossary term '{expected}' for '{term.source}'"
                    )
        return warnings
