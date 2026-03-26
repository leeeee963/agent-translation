from __future__ import annotations

import logging
import os
import re
from pathlib import Path

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser

logger = logging.getLogger(__name__)

_ASS_TAG_RE = re.compile(r"\{[^}]*\}")


class AssParser(BaseParser):
    """Parser for Advanced SubStation Alpha (.ass) subtitle files."""

    EXTENSIONS = {".ass"}

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.EXTENSIONS

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------
    def parse(self, file_path: str) -> ParsedFile:
        raw = Path(file_path).read_text(encoding="utf-8-sig")
        lines = raw.splitlines()

        header_lines, event_lines, format_parts, text_col_idx = self._split_sections(lines)

        blocks: list[ContentBlock] = []
        total_words = 0

        for idx, line in enumerate(event_lines):
            if not line.lower().startswith("dialogue:"):
                continue

            parts = line.split(",", len(format_parts) - 1)
            if len(parts) < len(format_parts):
                logger.warning("Skipping malformed Dialogue line %d", idx)
                continue

            raw_text = parts[text_col_idx]
            clean_text = _ASS_TAG_RE.sub("", raw_text).strip()
            if not clean_text:
                continue

            total_words += len(clean_text.split())
            blocks.append(
                ContentBlock(
                    id=f"ass_{idx}",
                    type=BlockType.SUBTITLE,
                    source_text=clean_text,
                    metadata={
                        "index": idx,
                        "original_line": line,
                        "text_col_index": text_col_idx,
                        "format_col_count": len(format_parts),
                    },
                )
            )

        return ParsedFile(
            meta=FileMeta(
                original_name=os.path.basename(file_path),
                file_type="ass",
                word_count=total_words,
            ),
            blocks=blocks,
            format_template={"header": header_lines, "event_lines": event_lines},
        )

    @staticmethod
    def _split_sections(lines: list[str]) -> tuple[list[str], list[str], list[str], int]:
        """Return (header_lines, event_lines, format_parts, text_column_index)."""
        header_lines: list[str] = []
        event_lines: list[str] = []
        in_events = False
        format_parts: list[str] = []
        text_col_idx = -1

        for line in lines:
            stripped = line.strip()
            if stripped.lower() == "[events]":
                in_events = True
                header_lines.append(line)
                continue

            if in_events and stripped.lower().startswith("format:"):
                header_lines.append(line)
                format_parts = [p.strip().lower() for p in stripped[len("format:"):].split(",")]
                text_col_idx = format_parts.index("text") if "text" in format_parts else len(format_parts) - 1
                continue

            if in_events and stripped:
                event_lines.append(line)
            else:
                if not in_events:
                    header_lines.append(line)

        if text_col_idx == -1:
            text_col_idx = 9
            format_parts = ["layer", "start", "end", "style", "name", "marginl", "marginr", "marginv", "effect", "text"]

        return header_lines, event_lines, format_parts, text_col_idx

    # ------------------------------------------------------------------
    # rebuild
    # ------------------------------------------------------------------
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        template = parsed_file.format_template
        if not template:
            raise ValueError("format_template is required for ASS rebuild")

        header_lines: list[str] = list(template["header"])
        event_lines: list[str] = list(template["event_lines"])

        block_by_idx: dict[int, ContentBlock] = {
            b.metadata["index"]: b for b in parsed_file.blocks if b.type == BlockType.SUBTITLE
        }

        rebuilt_events: list[str] = []
        for idx, line in enumerate(event_lines):
            block = block_by_idx.get(idx)
            if block is None:
                rebuilt_events.append(line)
                continue

            translated = self._best_text(block)
            if translated == block.source_text:
                rebuilt_events.append(line)
                continue

            col_count = block.metadata["format_col_count"]
            text_col = block.metadata["text_col_index"]
            parts = line.split(",", col_count - 1)

            raw_original = parts[text_col]
            new_text = self._replace_text_preserve_tags(raw_original, translated)
            parts[text_col] = new_text
            rebuilt_events.append(",".join(parts))

        output_lines = header_lines + rebuilt_events
        Path(output_path).write_text("\n".join(output_lines), encoding="utf-8")
        logger.info("Rebuilt ASS saved to %s", output_path)
        return output_path

    @staticmethod
    def _replace_text_preserve_tags(raw_text: str, translated: str) -> str:
        """Replace the visible text while keeping leading ASS override tags."""
        tags: list[str] = []
        rest = raw_text
        while rest.startswith("{"):
            end = rest.find("}")
            if end == -1:
                break
            tags.append(rest[: end + 1])
            rest = rest[end + 1:]

        return "".join(tags) + translated
