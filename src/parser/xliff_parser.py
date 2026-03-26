"""XLIFF (.xliff / .xlf) parser — standard localization exchange format.

Supports both XLIFF 1.2 (``<trans-unit>``) and XLIFF 2.0 (``<unit>``).
Uses ``lxml`` which is already a project dependency.

Design decisions
----------------
- Units with ``translate="no"`` are skipped.
- The ``id`` attribute is stored in ``metadata["trans_unit_id"]``.
- Inline tags (``<g>``, ``<x>``, ``<ph>``) are passed through as-is; the
  LLM prompt instructs it to preserve them unchanged.
- Rebuild sets ``<target>`` text and ``state="translated"`` on each unit.
"""

from __future__ import annotations

import copy
import logging
import os
from pathlib import Path

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser
from src.utils.text_filters import is_translatable

logger = logging.getLogger(__name__)

# XLIFF 1.2 namespace
_XLIFF_12_NS = "urn:oasis:names:tc:xliff:document:1.2"
# XLIFF 2.0 namespace
_XLIFF_20_NS = "urn:oasis:names:tc:xliff:document:2.0"


def _inner_text(element) -> str:
    """Return the text content of an element including tail text of children."""
    from lxml import etree
    parts = []
    if element.text:
        parts.append(element.text)
    for child in element:
        if isinstance(child.tag, str):
            # include the child's tag as placeholder marker text
            tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
            child_id = child.get("id", "")
            parts.append(f"<{tag}{f' id={child_id!r}' if child_id else ''} />")
        if child.tail:
            parts.append(child.tail)
    return "".join(parts)


class XliffParser(BaseParser):
    """Parser for XLIFF localization files (.xliff / .xlf)."""

    EXTENSIONS = {".xliff", ".xlf"}

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.EXTENSIONS

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------
    def parse(self, file_path: str) -> ParsedFile:
        try:
            from lxml import etree
        except ImportError as exc:
            raise ImportError("lxml is required for XLIFF support.") from exc

        tree = etree.parse(file_path)
        root = tree.getroot()
        ns = root.nsmap.get(None, "")

        blocks: list[ContentBlock] = []
        word_count = 0

        if _XLIFF_12_NS in ns or "xliff" in root.tag:
            blocks, word_count = self._parse_12(root)
        else:
            blocks, word_count = self._parse_20(root)

        raw_bytes = Path(file_path).read_bytes()
        return ParsedFile(
            meta=FileMeta(
                original_name=os.path.basename(file_path),
                file_type=Path(file_path).suffix.lstrip("."),
                word_count=word_count,
            ),
            blocks=blocks,
            format_template={"path": file_path, "raw": raw_bytes, "version": "1.2" if _XLIFF_12_NS in ns else "2.0"},
        )

    def _parse_12(self, root) -> tuple[list[ContentBlock], int]:
        blocks: list[ContentBlock] = []
        word_count = 0
        ns = {"x": _XLIFF_12_NS}

        for tu in root.findall(".//x:trans-unit", ns):
            if tu.get("translate") == "no":
                continue
            tu_id = tu.get("id", "")
            source_elem = tu.find("x:source", ns)
            if source_elem is None:
                continue
            source_text = _inner_text(source_elem)
            if not is_translatable(source_text):
                continue
            bid = f"tu_{tu_id}"
            blocks.append(ContentBlock(
                id=bid,
                type=BlockType.TRANSLATION_UNIT,
                source_text=source_text,
                metadata={"trans_unit_id": tu_id, "version": "1.2"},
            ))
            word_count += len(source_text.split())

        return blocks, word_count

    def _parse_20(self, root) -> tuple[list[ContentBlock], int]:
        blocks: list[ContentBlock] = []
        word_count = 0
        # XLIFF 2.0: <unit id="..."><segment><source>...
        for unit in root.iter():
            tag = unit.tag.split("}")[-1] if "}" in unit.tag else unit.tag
            if tag != "unit":
                continue
            if unit.get("translate") == "no":
                continue
            unit_id = unit.get("id", "")
            for seg in unit:
                seg_tag = seg.tag.split("}")[-1] if "}" in seg.tag else seg.tag
                if seg_tag != "segment":
                    continue
                for src in seg:
                    src_tag = src.tag.split("}")[-1] if "}" in src.tag else src.tag
                    if src_tag == "source":
                        source_text = _inner_text(src)
                        if not is_translatable(source_text):
                            continue
                        bid = f"unit_{unit_id}"
                        blocks.append(ContentBlock(
                            id=bid,
                            type=BlockType.TRANSLATION_UNIT,
                            source_text=source_text,
                            metadata={"trans_unit_id": unit_id, "version": "2.0"},
                        ))
                        word_count += len(source_text.split())

        return blocks, word_count

    # ------------------------------------------------------------------
    # rebuild
    # ------------------------------------------------------------------
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        try:
            from lxml import etree
        except ImportError as exc:
            raise ImportError("lxml is required for XLIFF support.") from exc

        template = parsed_file.format_template or {}
        original_path = template.get("path", "")
        version = template.get("version", "1.2")

        if not original_path or not os.path.exists(original_path):
            raise FileNotFoundError(f"Original XLIFF not found: {original_path}")

        tree = etree.parse(original_path)
        root = tree.getroot()
        block_map: dict[str, ContentBlock] = {b.id: b for b in parsed_file.blocks}

        if version == "1.2":
            self._rebuild_12(root, block_map)
        else:
            self._rebuild_20(root, block_map)

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        tree.write(output_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
        logger.info("Rebuilt XLIFF saved to %s", output_path)
        return output_path

    @staticmethod
    def _rebuild_12(root, block_map: dict[str, ContentBlock]) -> None:
        from lxml import etree
        ns = {"x": _XLIFF_12_NS}
        for tu in root.findall(".//x:trans-unit", ns):
            tu_id = tu.get("id", "")
            bid = f"tu_{tu_id}"
            block = block_map.get(bid)
            if not block:
                continue
            translated = BaseParser._best_text(block)
            if not translated:
                continue
            target_elem = tu.find("x:target", ns)
            if target_elem is None:
                target_elem = etree.SubElement(tu, f"{{{_XLIFF_12_NS}}}target")
            target_elem.text = translated
            target_elem.set("state", "translated")

    @staticmethod
    def _rebuild_20(root, block_map: dict[str, ContentBlock]) -> None:
        from lxml import etree
        for unit in root.iter():
            tag = unit.tag.split("}")[-1] if "}" in unit.tag else unit.tag
            if tag != "unit":
                continue
            unit_id = unit.get("id", "")
            bid = f"unit_{unit_id}"
            block = block_map.get(bid)
            if not block:
                continue
            translated = BaseParser._best_text(block)
            if not translated:
                continue
            # Find or create <target> within <segment>
            unit_ns = unit.tag.rsplit("}", 1)[0].lstrip("{") if "}" in unit.tag else _XLIFF_20_NS
            for seg in unit:
                seg_tag = seg.tag.split("}")[-1] if "}" in seg.tag else seg.tag
                if seg_tag != "segment":
                    continue
                target_elem = None
                for child in seg:
                    c_tag = child.tag.split("}")[-1] if "}" in child.tag else child.tag
                    if c_tag == "target":
                        target_elem = child
                        break
                if target_elem is None:
                    target_elem = etree.SubElement(seg, f"{{{unit_ns}}}target")
                target_elem.text = translated
                seg.set("state", "translated")
