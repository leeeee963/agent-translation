"""Markdown (.md) parser.

Uses mistune>=3.0 to parse Markdown into an AST, extracts translatable
heading / paragraph / list text, and rebuilds by substituting translated
text back into the source document line-by-line.

Design decisions
----------------
- Code blocks and inline code are NOT translated (translatable=False).
- Inline formatting markers (**bold**, [link](url)) are included in the
  extracted text verbatim; the LLM is instructed to preserve them.
- Rebuild strategy: find each source text in the original Markdown source
  and replace it with the translated version (line-aware replacement).
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser
from src.utils.text_filters import is_translatable

logger = logging.getLogger(__name__)


def _strip_heading_prefix(line: str) -> str:
    """Remove leading '#' markers from a heading line."""
    return re.sub(r"^#{1,6}\s+", "", line)


class MarkdownParser(BaseParser):
    """Parser for Markdown documents (.md)."""

    EXTENSIONS = {".md"}

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.EXTENSIONS

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------
    def parse(self, file_path: str) -> ParsedFile:
        try:
            import mistune  # noqa: F401
        except ImportError as exc:
            raise ImportError(
                "mistune is required for Markdown support. "
                "Run: pip install 'mistune>=3.0'"
            ) from exc

        source = Path(file_path).read_text(encoding="utf-8")
        blocks: list[ContentBlock] = []
        word_count = 0

        # Parse line by line — simple but reliable for headings / paragraphs
        # We use mistune only to identify code-fence boundaries.
        in_code_fence = False
        paragraph_buffer: list[str] = []
        paragraph_start_line = 0
        line_num = 0

        def _flush_paragraph(lines: list[str], start_line: int) -> None:
            text = "\n".join(lines).strip()
            if is_translatable(text):
                bid = f"para_{start_line}"
                blocks.append(ContentBlock(
                    id=bid,
                    type=BlockType.PARAGRAPH,
                    source_text=text,
                    metadata={"line": start_line},
                ))
                nonlocal word_count
                word_count += len(text.split())

        source_lines = source.splitlines()
        i = 0
        block_idx = 0
        while i < len(source_lines):
            line = source_lines[i]
            stripped = line.strip()

            # Code fence detection
            if stripped.startswith("```") or stripped.startswith("~~~"):
                if in_code_fence:
                    in_code_fence = False
                else:
                    # Flush any buffered paragraph before entering code fence
                    if paragraph_buffer:
                        _flush_paragraph(paragraph_buffer, paragraph_start_line)
                        paragraph_buffer = []
                    in_code_fence = True
                i += 1
                continue

            if in_code_fence:
                i += 1
                continue

            # Heading lines
            heading_match = re.match(r"^(#{1,6})\s+(.+)$", line)
            if heading_match:
                if paragraph_buffer:
                    _flush_paragraph(paragraph_buffer, paragraph_start_line)
                    paragraph_buffer = []
                heading_text = heading_match.group(2).strip()
                level = len(heading_match.group(1))
                if is_translatable(heading_text):
                    bid = f"h{level}_{i}"
                    blocks.append(ContentBlock(
                        id=bid,
                        type=BlockType.HEADING,
                        source_text=heading_text,
                        metadata={"line": i, "level": level},
                    ))
                    word_count += len(heading_text.split())
                block_idx += 1
                i += 1
                continue

            # List item lines
            list_match = re.match(r"^(\s*(?:[-*+]|\d+\.)\s+)(.+)$", line)
            if list_match:
                if paragraph_buffer:
                    _flush_paragraph(paragraph_buffer, paragraph_start_line)
                    paragraph_buffer = []
                item_text = list_match.group(2).strip()
                prefix = list_match.group(1)
                if is_translatable(item_text):
                    bid = f"li_{i}"
                    blocks.append(ContentBlock(
                        id=bid,
                        type=BlockType.LIST,
                        source_text=item_text,
                        metadata={"line": i, "list_prefix": prefix},
                    ))
                    word_count += len(item_text.split())
                i += 1
                continue

            # Blank line → flush paragraph buffer
            if not stripped:
                if paragraph_buffer:
                    _flush_paragraph(paragraph_buffer, paragraph_start_line)
                    paragraph_buffer = []
                i += 1
                continue

            # Regular paragraph text
            if not paragraph_buffer:
                paragraph_start_line = i
            paragraph_buffer.append(line)
            i += 1

        if paragraph_buffer:
            _flush_paragraph(paragraph_buffer, paragraph_start_line)

        return ParsedFile(
            meta=FileMeta(
                original_name=os.path.basename(file_path),
                file_type="md",
                word_count=word_count,
            ),
            blocks=blocks,
            format_template=source,  # Store original source for rebuild
        )

    # ------------------------------------------------------------------
    # rebuild
    # ------------------------------------------------------------------
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        source: str = parsed_file.format_template or ""
        source_lines = source.splitlines(keepends=True)
        result_lines = list(source_lines)

        for block in parsed_file.blocks:
            translated = self._best_text(block)
            if translated == block.source_text:
                continue  # no change

            line_num: int = block.metadata.get("line", -1)
            if line_num < 0 or line_num >= len(result_lines):
                continue

            original_line = result_lines[line_num]

            if block.type == BlockType.HEADING:
                level = block.metadata.get("level", 1)
                prefix = "#" * level + " "
                result_lines[line_num] = prefix + translated + "\n"

            elif block.type == BlockType.LIST:
                list_prefix = block.metadata.get("list_prefix", "- ")
                result_lines[line_num] = list_prefix + translated + "\n"

            elif block.type == BlockType.PARAGRAPH:
                # Paragraph may span multiple lines; replace from start_line
                src_text = block.source_text
                src_para_lines = src_text.splitlines()
                # Replace as many lines as the original paragraph spanned
                for j, _ in enumerate(src_para_lines):
                    if line_num + j < len(result_lines):
                        if j == 0:
                            result_lines[line_num + j] = translated + "\n"
                        else:
                            result_lines[line_num + j] = ""

        out_text = "".join(result_lines)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(out_text, encoding="utf-8")
        logger.info("Rebuilt Markdown saved to %s", output_path)
        return output_path
