from __future__ import annotations

import logging

from src.models.content import ContentBlock

logger = logging.getLogger(__name__)


class Merger:
    """Merges translated segments back into the full block list."""

    def merge(
        self,
        segments: list[list[ContentBlock]],
        all_blocks: list[ContentBlock],
    ) -> list[ContentBlock]:
        translated_map: dict[str, str] = {}
        reviewed_map: dict[str, str] = {}
        for segment in segments:
            for block in segment:
                if block.translated_text:
                    translated_map[block.id] = block.translated_text
                if block.reviewed_text:
                    reviewed_map[block.id] = block.reviewed_text

        applied = 0
        for block in all_blocks:
            if block.id in translated_map:
                block.translated_text = translated_map[block.id]
                applied += 1
            if block.id in reviewed_map:
                block.reviewed_text = reviewed_map[block.id]

        logger.info(
            "Merged translations: %d/%d blocks updated",
            applied,
            len(all_blocks),
        )
        return all_blocks
