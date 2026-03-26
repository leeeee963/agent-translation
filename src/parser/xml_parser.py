"""XML (.xml) parser — Android string resources and generic app resources.

Uses ``lxml`` which is already a project dependency.

Design decisions
----------------
- Text leaf elements → KEY_VALUE blocks; ``name`` attribute used as key_path.
- Translatable attributes (``label``, ``title``, ``placeholder``, ``alt``,
  ``aria-label``, ``content``) are also extracted.
- Elements with ``translatable="false"`` or ``translate="no"`` are skipped.
- Rebuild uses lxml XPath to locate elements by their block id / key_path.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser
from src.utils.text_filters import is_translatable
from src.utils.xml_path import lxml_node_path, lxml_find_by_path

logger = logging.getLogger(__name__)

_TRANSLATABLE_ATTRS = {"label", "title", "placeholder", "alt", "aria-label", "content", "description"}
_SKIP_TAGS = {"script", "style", "code", "pre"}


class XmlParser(BaseParser):
    """Parser for XML files (.xml) — Android resources, app strings, etc."""

    EXTENSIONS = {".xml"}

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.EXTENSIONS

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------
    def parse(self, file_path: str) -> ParsedFile:
        try:
            from lxml import etree
        except ImportError as exc:
            raise ImportError("lxml is required for XML support.") from exc

        raw = Path(file_path).read_bytes()
        try:
            tree = etree.fromstring(raw)
        except etree.XMLSyntaxError as exc:
            raise ValueError(f"Invalid XML: {exc}") from exc

        blocks: list[ContentBlock] = []
        word_count = 0
        idx = 0

        def _visit(elem, depth: int = 0) -> None:
            nonlocal idx
            tag = elem.tag.split("}")[-1] if isinstance(elem.tag, str) and "}" in elem.tag else (elem.tag or "")
            if tag in _SKIP_TAGS:
                return
            if elem.get("translatable") == "false" or elem.get("translate") == "no":
                return

            # Element text content
            text = (elem.text or "").strip()
            if text and is_translatable(text) and not list(elem):
                # It's a leaf with text
                name_attr = elem.get("name", "")
                key_path = name_attr or lxml_node_path(elem)
                bid = f"xml_{idx}"
                idx += 1
                blocks.append(ContentBlock(
                    id=bid,
                    type=BlockType.KEY_VALUE,
                    source_text=text,
                    metadata={
                        "key_path": key_path,
                        "node_path": lxml_node_path(elem),
                        "attr": None,
                    },
                ))
                nonlocal word_count
                word_count += len(text.split())

            # Translatable attributes
            for attr_name in _TRANSLATABLE_ATTRS:
                attr_val = elem.get(attr_name, "").strip()
                if attr_val and is_translatable(attr_val):
                    bid = f"xml_attr_{idx}"
                    idx += 1
                    blocks.append(ContentBlock(
                        id=bid,
                        type=BlockType.KEY_VALUE,
                        source_text=attr_val,
                        metadata={
                            "key_path": f"{lxml_node_path(elem)}@{attr_name}",
                            "node_path": lxml_node_path(elem),
                            "attr": attr_name,
                        },
                    ))
                    word_count += len(attr_val.split())

            for child in elem:
                _visit(child, depth + 1)

        _visit(tree)

        return ParsedFile(
            meta=FileMeta(
                original_name=os.path.basename(file_path),
                file_type="xml",
                word_count=word_count,
            ),
            blocks=blocks,
            format_template=file_path,
        )

    # ------------------------------------------------------------------
    # rebuild
    # ------------------------------------------------------------------
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        try:
            from lxml import etree
        except ImportError as exc:
            raise ImportError("lxml is required for XML support.") from exc

        original_path = parsed_file.format_template
        if not original_path or not os.path.exists(original_path):
            raise FileNotFoundError(f"Original XML not found: {original_path}")

        raw = Path(original_path).read_bytes()
        root = etree.fromstring(raw)

        for block in parsed_file.blocks:
            translated = self._best_text(block)
            if translated == block.source_text:
                continue
            node_path = block.metadata.get("node_path", "")
            attr = block.metadata.get("attr")
            if not node_path:
                continue
            elem = lxml_find_by_path(root, node_path)
            if elem is None:
                logger.warning("Could not locate node at path '%s'", node_path)
                continue
            if attr:
                elem.set(attr, translated)
            else:
                elem.text = translated

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        tree = etree.ElementTree(root)
        tree.write(output_path, encoding="utf-8", xml_declaration=True, pretty_print=True)
        logger.info("Rebuilt XML saved to %s", output_path)
        return output_path
