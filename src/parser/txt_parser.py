"""Plain text (.txt) parser.

Splits the file into paragraphs separated by blank lines. Each non-empty
paragraph becomes a translatable block. Rebuild substitutes the translated
text back at the original line offsets, preserving blank lines and the
original line endings as much as possible.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser
from src.utils.text_filters import is_translatable

logger = logging.getLogger(__name__)


class TxtParser(BaseParser):
    """Parser for plain text documents (.txt)."""

    EXTENSIONS = {".txt", ".text"}

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.EXTENSIONS

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------
    def parse(self, file_path: str) -> ParsedFile:
        # Read with utf-8, fall back to utf-8-sig / latin-1 for robustness.
        raw_bytes = Path(file_path).read_bytes()
        try:
            source = raw_bytes.decode("utf-8-sig")
        except UnicodeDecodeError:
            source = raw_bytes.decode("latin-1")

        blocks: list[ContentBlock] = []
        word_count = 0

        source_lines = source.splitlines()
        paragraph_buffer: list[str] = []
        paragraph_start_line = 0

        def _flush(start_line: int) -> None:
            nonlocal word_count
            if not paragraph_buffer:
                return
            text = "\n".join(paragraph_buffer).strip()
            if is_translatable(text):
                blocks.append(ContentBlock(
                    id=f"para_{start_line}",
                    type=BlockType.PARAGRAPH,
                    source_text=text,
                    metadata={"line": start_line, "span": len(paragraph_buffer)},
                ))
                word_count += len(text.split())

        for i, line in enumerate(source_lines):
            if not line.strip():
                _flush(paragraph_start_line)
                paragraph_buffer.clear()
                continue
            if not paragraph_buffer:
                paragraph_start_line = i
            paragraph_buffer.append(line)

        _flush(paragraph_start_line)

        return ParsedFile(
            meta=FileMeta(
                original_name=os.path.basename(file_path),
                file_type="txt",
                word_count=word_count,
            ),
            blocks=blocks,
            format_template=source,
        )

    # ------------------------------------------------------------------
    # rebuild
    # ------------------------------------------------------------------
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        source: str = parsed_file.format_template or ""
        result_lines = source.splitlines()

        for block in parsed_file.blocks:
            translated = self._best_text(block)
            if translated == block.source_text:
                continue
            line_num: int = block.metadata.get("line", -1)
            span: int = block.metadata.get("span", 1)
            if line_num < 0 or line_num >= len(result_lines):
                continue
            # Replace first line with full translation, blank out the rest.
            result_lines[line_num] = translated
            for j in range(1, span):
                if line_num + j < len(result_lines):
                    result_lines[line_num + j] = ""

        out_text = "\n".join(result_lines)
        if source.endswith("\n"):
            out_text += "\n"

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(out_text, encoding="utf-8")
        logger.info("Rebuilt TXT saved to %s", output_path)
        return output_path
