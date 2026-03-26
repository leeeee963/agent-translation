"""JSON (.json) parser — i18n resource files.

Design decisions
----------------
- Recursively traverses the JSON tree; all string leaf nodes become
  KEY_VALUE blocks with ``metadata["key_path"]`` set to the dot-path.
- Keys listed in ``JSON_SKIP_KEYS`` are excluded from translation.
- ``{placeholder}`` tokens in values are preserved by the LLM prompt system.
- Rebuild navigates the original parsed dict by key_path and replaces the
  string value before dumping with ``json.dumps(ensure_ascii=False)``.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser
from src.utils.key_path import iter_leaf_strings, set_by_path
from src.utils.text_filters import is_translatable

logger = logging.getLogger(__name__)

# Keys whose values are almost never translatable human-readable text
JSON_SKIP_KEYS: set[str] = {
    "url", "href", "src", "id", "uuid", "guid", "key", "name",
    "version", "color", "colour", "type", "format", "icon",
    "class", "className", "style", "lang", "locale", "currency",
    "email", "phone", "date", "time", "timestamp",
}


class JsonParser(BaseParser):
    """Parser for JSON i18n resource files (.json)."""

    EXTENSIONS = {".json"}

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.EXTENSIONS

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------
    def parse(self, file_path: str) -> ParsedFile:
        raw = Path(file_path).read_text(encoding="utf-8")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON file: {exc}") from exc

        blocks: list[ContentBlock] = []
        word_count = 0

        for key_path, value in iter_leaf_strings(data, skip_keys=JSON_SKIP_KEYS):
            # Additional per-value heuristics
            if not is_translatable(value):
                continue
            # Skip values that look like identifiers / codes
            if _looks_like_key(key_path, value):
                continue

            bid = key_path.replace(".", "_").replace("[", "").replace("]", "")
            blocks.append(ContentBlock(
                id=bid,
                type=BlockType.KEY_VALUE,
                source_text=value,
                metadata={"key_path": key_path},
            ))
            word_count += len(value.split())

        import copy
        return ParsedFile(
            meta=FileMeta(
                original_name=os.path.basename(file_path),
                file_type="json",
                word_count=word_count,
            ),
            blocks=blocks,
            format_template=copy.deepcopy(data),
        )

    # ------------------------------------------------------------------
    # rebuild
    # ------------------------------------------------------------------
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        import copy
        data = copy.deepcopy(parsed_file.format_template)

        for block in parsed_file.blocks:
            translated = self._best_text(block)
            key_path: str = block.metadata.get("key_path", "")
            if not key_path:
                continue
            try:
                set_by_path(data, key_path, translated)
            except (KeyError, IndexError, ValueError) as exc:
                logger.warning("Could not set key_path '%s': %s", key_path, exc)

        out_text = json.dumps(data, ensure_ascii=False, indent=2)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(out_text, encoding="utf-8")
        logger.info("Rebuilt JSON saved to %s", output_path)
        return output_path


def _looks_like_key(key_path: str, value: str) -> bool:
    """Heuristic: return True if the value looks like a code/key rather than text."""
    # Last segment of the path is a known skip keyword
    last_key = key_path.rsplit(".", 1)[-1].lower()
    if last_key in JSON_SKIP_KEYS:
        return True
    # Value is a single word with no spaces and no CJK — likely a code
    if " " not in value and len(value) < 30 and value.isidentifier():
        return True
    return False
