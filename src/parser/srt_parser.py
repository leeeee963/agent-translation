from __future__ import annotations

import logging
import os
from pathlib import Path

import pysrt

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser

logger = logging.getLogger(__name__)


class SrtParser(BaseParser):
    """Parser for SubRip (.srt) subtitle files."""

    EXTENSIONS = {".srt"}

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.EXTENSIONS

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------
    def parse(self, file_path: str) -> ParsedFile:
        # Use utf-8-sig to transparently strip a UTF-8 BOM if present;
        # otherwise pysrt reads "\ufeff1" as the first index and int() fails.
        subs = pysrt.open(file_path, encoding="utf-8-sig")
        blocks: list[ContentBlock] = []
        total_words = 0

        for item in subs:
            text = item.text.strip()
            if not text:
                continue
            total_words += len(text.split())
            blocks.append(
                ContentBlock(
                    id=f"srt_{item.index}",
                    type=BlockType.SUBTITLE,
                    source_text=text,
                    metadata={
                        "index": item.index,
                        "start": str(item.start),
                        "end": str(item.end),
                    },
                )
            )

        return ParsedFile(
            meta=FileMeta(
                original_name=os.path.basename(file_path),
                file_type="srt",
                word_count=total_words,
            ),
            blocks=blocks,
            format_template=None,
        )

    # ------------------------------------------------------------------
    # rebuild
    # ------------------------------------------------------------------
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        lines: list[str] = []
        for block in parsed_file.blocks:
            if block.type != BlockType.SUBTITLE:
                continue
            meta = block.metadata
            text = self._best_text(block)
            lines.append(str(meta["index"]))
            lines.append(f"{meta['start']} --> {meta['end']}")
            lines.append(text)
            lines.append("")

        Path(output_path).write_text("\n".join(lines), encoding="utf-8")
        logger.info("Rebuilt SRT saved to %s", output_path)
        return output_path
