from __future__ import annotations

import logging
import os
from pathlib import Path

import webvtt

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser

logger = logging.getLogger(__name__)


class VttParser(BaseParser):
    """Parser for WebVTT (.vtt) subtitle files."""

    EXTENSIONS = {".vtt"}

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.EXTENSIONS

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------
    def parse(self, file_path: str) -> ParsedFile:
        captions = webvtt.read(file_path)
        blocks: list[ContentBlock] = []
        total_words = 0

        for idx, caption in enumerate(captions):
            text = caption.text.strip()
            if not text:
                continue
            total_words += len(text.split())
            blocks.append(
                ContentBlock(
                    id=f"vtt_{idx}",
                    type=BlockType.SUBTITLE,
                    source_text=text,
                    metadata={
                        "index": idx,
                        "start": caption.start,
                        "end": caption.end,
                    },
                )
            )

        return ParsedFile(
            meta=FileMeta(
                original_name=os.path.basename(file_path),
                file_type="vtt",
                word_count=total_words,
            ),
            blocks=blocks,
            format_template=None,
        )

    # ------------------------------------------------------------------
    # rebuild
    # ------------------------------------------------------------------
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        lines: list[str] = ["WEBVTT", ""]
        for block in parsed_file.blocks:
            if block.type != BlockType.SUBTITLE:
                continue
            meta = block.metadata
            text = self._best_text(block)
            lines.append(f"{meta['start']} --> {meta['end']}")
            lines.append(text)
            lines.append("")

        Path(output_path).write_text("\n".join(lines), encoding="utf-8")
        logger.info("Rebuilt VTT saved to %s", output_path)
        return output_path
