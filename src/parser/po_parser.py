"""PO / POT (.po / .pot) parser — GNU gettext translation files.

Uses ``polib>=1.2.0`` to read and write PO files.

Design decisions
----------------
- Extracts both untranslated entries (``msgstr == ""``) and already-translated
  entries so the file can be re-translated or updated.
- Each entry becomes a ``TRANSLATION_UNIT`` block.
- ``msgctxt`` is stored in ``metadata["msgctxt"]`` to aid disambiguation.
- Rebuild writes translated ``msgstr`` back through polib and saves the file.
- ``fuzzy`` flag is removed from entries that receive a new translation.
- Plural forms: ``msgstr[0]`` is filled with the main translation;
  plural variants beyond index 0 are left to the LLM (passed as context).
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser
from src.utils.text_filters import is_translatable

logger = logging.getLogger(__name__)


class PoParser(BaseParser):
    """Parser for GNU gettext PO/POT files (.po / .pot)."""

    EXTENSIONS = {".po", ".pot"}

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.EXTENSIONS

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------
    def parse(self, file_path: str) -> ParsedFile:
        try:
            import polib
        except ImportError as exc:
            raise ImportError(
                "polib is required for PO/POT support. "
                "Run: pip install 'polib>=1.2.0'"
            ) from exc

        po = polib.pofile(file_path)
        blocks: list[ContentBlock] = []
        word_count = 0

        for entry in po:
            msgid = entry.msgid.strip()
            if not msgid or not is_translatable(msgid):
                continue

            meta: dict = {
                "msgid": msgid,
                "occurrences": entry.occurrences,
            }
            if entry.msgctxt:
                meta["msgctxt"] = entry.msgctxt
            if entry.msgid_plural:
                meta["msgid_plural"] = entry.msgid_plural
            if entry.flags:
                meta["flags"] = list(entry.flags)

            bid = _make_block_id(msgid, entry.msgctxt)
            blocks.append(ContentBlock(
                id=bid,
                type=BlockType.TRANSLATION_UNIT,
                source_text=msgid,
                metadata=meta,
            ))
            word_count += len(msgid.split())

        return ParsedFile(
            meta=FileMeta(
                original_name=os.path.basename(file_path),
                file_type=Path(file_path).suffix.lstrip("."),
                word_count=word_count,
            ),
            blocks=blocks,
            format_template=file_path,  # path to original — polib re-reads it
        )

    # ------------------------------------------------------------------
    # rebuild
    # ------------------------------------------------------------------
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        try:
            import polib
        except ImportError as exc:
            raise ImportError("polib is required for PO/POT support.") from exc

        original_path = parsed_file.format_template
        if not original_path or not os.path.exists(original_path):
            raise FileNotFoundError(f"Original PO file not found: {original_path}")

        po = polib.pofile(original_path)
        block_map: dict[str, ContentBlock] = {b.id: b for b in parsed_file.blocks}

        for entry in po:
            msgid = entry.msgid.strip()
            if not msgid:
                continue
            bid = _make_block_id(msgid, entry.msgctxt)
            block = block_map.get(bid)
            if not block:
                continue
            translated = self._best_text(block)
            if translated and translated != msgid:
                if entry.msgid_plural:
                    # Fill msgstr[0]; leave others if not provided
                    entry.msgstr_plural = entry.msgstr_plural or {}
                    entry.msgstr_plural[0] = translated
                else:
                    entry.msgstr = translated
                # Remove fuzzy flag
                if "fuzzy" in (entry.flags or []):
                    entry.flags.remove("fuzzy")

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        po.save(output_path)
        logger.info("Rebuilt PO saved to %s", output_path)
        return output_path


def _make_block_id(msgid: str, msgctxt: str | None = None) -> str:
    """Create a stable block id from msgid (and optional msgctxt)."""
    import hashlib
    key = f"{msgctxt or ''}::{msgid}"
    return "po_" + hashlib.md5(key.encode()).hexdigest()[:12]
