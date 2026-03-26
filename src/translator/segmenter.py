"""Semantic segmenter for translation context windows."""

from __future__ import annotations

import logging
import re

from src.models.content import BlockType, ContentBlock

logger = logging.getLogger(__name__)

_CJK_RANGE = re.compile(
    r"[\u2e80-\u9fff\uf900-\ufaff\U00020000-\U0002fa1f]"
)
_SENTENCE_END = re.compile(r"[.!?。！？…]\s*$")


def _estimate_tokens(text: str) -> float:
    """Rough token count: CJK chars / 2, latin words * 1.3."""
    cjk_chars = len(_CJK_RANGE.findall(text))
    non_cjk = _CJK_RANGE.sub("", text)
    latin_words = len(non_cjk.split())
    return cjk_chars / 2 + latin_words * 1.3


def _get_slide_index(block: ContentBlock) -> int | None:
    si = block.metadata.get("slide_index")
    if si is not None:
        return int(si)
    m = re.match(r"slide(\d+)", block.id)
    return int(m.group(1)) if m else None


def _time_to_seconds(value: str | None) -> float | None:
    if not value:
        return None

    match = re.match(
        r"(?P<h>\d+):(?P<m>\d+):(?P<s>\d+)(?P<sep>[:,.])(?P<ms>\d+)",
        value,
    )
    if not match:
        return None

    h = int(match.group("h"))
    m = int(match.group("m"))
    s = int(match.group("s"))
    ms = int(match.group("ms")[:3].ljust(3, "0"))
    return h * 3600 + m * 60 + s + ms / 1000


def _is_subtitle(block: ContentBlock) -> bool:
    return block.type == BlockType.SUBTITLE


def _is_keyvalue_block(block: ContentBlock) -> bool:
    return block.type in (BlockType.KEY_VALUE, BlockType.TRANSLATION_UNIT)


def _is_slide_block(block: ContentBlock) -> bool:
    return block.type in (
        BlockType.HEADING,
        BlockType.PARAGRAPH,
        BlockType.SLIDE_NOTE,
    ) and (_get_slide_index(block) is not None)


class Segmenter:
    """Groups consecutive translatable blocks into semantically useful segments."""

    def segment(
        self,
        blocks: list[ContentBlock],
        *,
        file_type: str = "",
        max_tokens: int = 2000,
        options: dict | None = None,
    ) -> list[list[ContentBlock]]:
        if not blocks:
            return []

        options = options or {}

        if file_type == "pptx" or _is_slide_block(blocks[0]):
            segments = self._segment_slides(
                blocks,
                max_tokens,
                max_slides_per_segment=int(options.get("slide_cluster_pages", 2)),
            )
        elif file_type in {"srt", "vtt", "ass"} or _is_subtitle(blocks[0]):
            segments = self._segment_subtitles(
                blocks,
                max_tokens,
                target_group_size=int(options.get("subtitle_window_size", 12)),
                max_gap_seconds=float(options.get("subtitle_max_gap_seconds", 5.0)),
            )
        elif file_type in {"json", "yaml", "yml", "po", "pot", "xliff", "xlf", "xml"} or _is_keyvalue_block(blocks[0]):
            segments = self._segment_keyvalue(
                blocks,
                max_tokens,
                preferred_cluster_size=int(options.get("doc_paragraph_cluster_size", 12)),
            )
        else:
            segments = self._segment_general(
                blocks,
                max_tokens,
                preferred_cluster_size=int(options.get("doc_paragraph_cluster_size", 12)),
            )

        logger.info(
            "Segmented %d blocks into %d segments (max_tokens=%d)",
            len(blocks),
            len(segments),
            max_tokens,
        )
        return segments

    def build_context_hints(
        self,
        segments: list[list[ContentBlock]],
        idx: int,
        previous_summary: str,
        context_window_size: int = 500,
        preview_chars: int = 350,
    ) -> dict[str, str]:
        """Build context hints for segment at `idx`."""
        hints: dict[str, str] = {}

        if previous_summary:
            hints["previous_summary"] = (
                "Previous translated context (for continuity, do not repeat verbatim):\n"
                f"{previous_summary[-context_window_size:]}"
            )

        if idx + 1 < len(segments):
            next_text = "\n".join(b.source_text for b in segments[idx + 1])[:preview_chars]
            hints["next_preview"] = (
                "Upcoming source context (for coherence only, do NOT translate here):\n"
                f"{next_text}"
            )

        parts = [value for value in hints.values() if value]
        hints["combined"] = "\n\n".join(parts) if parts else ""
        return hints

    def _segment_slides(
        self,
        blocks: list[ContentBlock],
        max_tokens: int,
        max_slides_per_segment: int,
    ) -> list[list[ContentBlock]]:
        slide_groups: dict[int, list[ContentBlock]] = {}
        for block in blocks:
            slide_groups.setdefault(_get_slide_index(block) or 0, []).append(block)

        segments: list[list[ContentBlock]] = []
        current: list[ContentBlock] = []
        current_tokens = 0.0
        current_slide_count = 0

        for slide_idx in sorted(slide_groups):
            slide_blocks = slide_groups[slide_idx]
            slide_tokens = sum(_estimate_tokens(b.source_text) for b in slide_blocks)

            if current and (
                current_tokens + slide_tokens > max_tokens
                or current_slide_count >= max_slides_per_segment
            ):
                segments.append(current)
                current = []
                current_tokens = 0.0
                current_slide_count = 0

            if slide_tokens > max_tokens and not current:
                segments.extend(self._segment_general(slide_blocks, max_tokens, 6))
                continue

            current.extend(slide_blocks)
            current_tokens += slide_tokens
            current_slide_count += 1

        if current:
            segments.append(current)
        return segments

    def _segment_subtitles(
        self,
        blocks: list[ContentBlock],
        max_tokens: int,
        target_group_size: int,
        max_gap_seconds: float,
    ) -> list[list[ContentBlock]]:
        segments: list[list[ContentBlock]] = []
        current: list[ContentBlock] = []
        current_tokens = 0.0

        for block in blocks:
            block_tokens = _estimate_tokens(block.source_text)
            current_end = _time_to_seconds(current[-1].metadata.get("end")) if current else None
            next_start = _time_to_seconds(block.metadata.get("start"))

            gap_break = (
                current
                and current_end is not None
                and next_start is not None
                and next_start - current_end > max_gap_seconds
            )
            size_break = len(current) >= target_group_size and _SENTENCE_END.search(
                current[-1].source_text
            )
            token_break = current and current_tokens + block_tokens > max_tokens

            if gap_break or size_break or token_break:
                segments.append(current)
                current = []
                current_tokens = 0.0

            current.append(block)
            current_tokens += block_tokens

        if current:
            segments.append(current)
        return segments

    def _segment_general(
        self,
        blocks: list[ContentBlock],
        max_tokens: int,
        preferred_cluster_size: int,
    ) -> list[list[ContentBlock]]:
        segments: list[list[ContentBlock]] = []
        current: list[ContentBlock] = []
        current_tokens = 0.0

        for block in blocks:
            block_tokens = _estimate_tokens(block.source_text)
            force_break = current and block.type == BlockType.HEADING
            soft_break = (
                current
                and len(current) >= preferred_cluster_size
                and _SENTENCE_END.search(current[-1].source_text)
            )

            if current and (force_break or soft_break or current_tokens + block_tokens > max_tokens):
                split_idx = self._find_best_split(current)
                if split_idx and split_idx < len(current):
                    segments.append(current[:split_idx])
                    current = current[split_idx:]
                    current_tokens = sum(
                        _estimate_tokens(item.source_text) for item in current
                    )
                else:
                    segments.append(current)
                    current = []
                    current_tokens = 0.0

            current.append(block)
            current_tokens += block_tokens

        if current:
            segments.append(current)
        return segments

    def _segment_keyvalue(
        self,
        blocks: list[ContentBlock],
        max_tokens: int,
        preferred_cluster_size: int,
    ) -> list[list[ContentBlock]]:
        """Group KEY_VALUE / TRANSLATION_UNIT blocks by namespace prefix.

        Blocks that share the same top-level key namespace (e.g. ``messages``
        in ``messages.button.submit``) are grouped together up to *max_tokens*.
        This keeps related strings in the same translation context.
        """
        segments: list[list[ContentBlock]] = []
        current: list[ContentBlock] = []
        current_tokens = 0.0
        current_ns: str | None = None

        for block in blocks:
            block_tokens = _estimate_tokens(block.source_text)
            key_path: str = block.metadata.get("key_path", "") or block.metadata.get("msgid", "")
            # Top-level namespace = first segment of dot-path
            ns = key_path.split(".")[0] if "." in key_path else ""

            ns_break = current and current_ns is not None and ns and ns != current_ns
            size_break = current and len(current) >= preferred_cluster_size
            token_break = current and current_tokens + block_tokens > max_tokens

            if ns_break or size_break or token_break:
                segments.append(current)
                current = []
                current_tokens = 0.0

            current.append(block)
            current_tokens += block_tokens
            current_ns = ns if ns else current_ns

        if current:
            segments.append(current)
        return segments

    @staticmethod
    def _find_best_split(blocks: list[ContentBlock]) -> int | None:
        if len(blocks) <= 1:
            return None

        for idx in range(len(blocks) - 1, 0, -1):
            if blocks[idx].type == BlockType.HEADING:
                return idx
            if _SENTENCE_END.search(blocks[idx - 1].source_text):
                return idx
        return None
