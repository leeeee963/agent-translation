"""HTML (.html / .htm) parser.

Uses BeautifulSoup4 with the lxml backend (already a dependency).

Design decisions
----------------
- ``<h1>``–``<h6>``  → HEADING blocks
- ``<p>``, ``<li>``, ``<td>``, ``<th>``, ``<button>``, ``<a>``, ``<label>``
  → PARAGRAPH blocks
- ``<script>``, ``<style>``, ``<code>``, ``<pre>`` → skipped entirely
- Elements with ``translate="no"`` → skipped
- Translatable attributes: ``alt``, ``placeholder``, ``title``
- ``metadata["node_path"]`` stores a CSS-like selector path used for
  reconstruction.  Rebuild re-parses the original HTML and locates each
  node by sequential index within its tag type.

Inline mixed content (``<p>Hello <strong>world</strong></p>``) is extracted
as a single block; the LLM is expected to preserve inline tags.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser
from src.utils.text_filters import is_translatable

logger = logging.getLogger(__name__)

_BLOCK_TAGS = {"p", "li", "td", "th", "button", "a", "label", "figcaption", "caption", "dt", "dd"}
_HEADING_TAGS = {"h1", "h2", "h3", "h4", "h5", "h6"}
_SKIP_TAGS = {"script", "style", "code", "pre", "svg", "math"}
_TRANSLATABLE_ATTRS = {"alt", "placeholder", "title"}


def _get_inner_html(tag) -> str:
    """Return inner HTML of a BS4 tag as a string."""
    return "".join(str(c) for c in tag.children)


def _tag_index(tag) -> int:
    """Return 1-based index of *tag* among siblings with the same name."""
    siblings = [s for s in tag.parent.children if getattr(s, "name", None) == tag.name]
    return siblings.index(tag) + 1


def _node_selector(tag) -> str:
    """Build a simple positional CSS-like path for *tag*."""
    parts = []
    node = tag
    while node and node.name and node.name not in {"html", "[document]"}:
        idx = _tag_index(node)
        parts.append(f"{node.name}:nth-of-type({idx})")
        node = node.parent
    parts.reverse()
    return " > ".join(parts)


class HtmlParser(BaseParser):
    """Parser for HTML files (.html / .htm)."""

    EXTENSIONS = {".html", ".htm"}

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.EXTENSIONS

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------
    def parse(self, file_path: str) -> ParsedFile:
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise ImportError(
                "beautifulsoup4 is required for HTML support. "
                "Run: pip install 'beautifulsoup4>=4.12'"
            ) from exc

        raw = Path(file_path).read_text(encoding="utf-8", errors="replace")
        soup = BeautifulSoup(raw, "lxml")

        blocks: list[ContentBlock] = []
        word_count = 0
        idx = 0

        # Remove skip-tag subtrees from consideration
        for skip in soup.find_all(_SKIP_TAGS):
            skip.decompose()

        def _visit(tag) -> None:
            nonlocal idx
            name = getattr(tag, "name", None)
            if name is None:
                return
            if tag.get("translate") == "no":
                return

            if name in _HEADING_TAGS:
                text = tag.get_text(separator=" ", strip=True)
                if is_translatable(text):
                    level = int(name[1])
                    bid = f"html_{idx}"
                    idx += 1
                    selector = _node_selector(tag)
                    blocks.append(ContentBlock(
                        id=bid,
                        type=BlockType.HEADING,
                        source_text=text,
                        metadata={"node_path": selector, "level": level, "attr": None},
                    ))
                    nonlocal word_count
                    word_count += len(text.split())
                # Don't recurse into heading children
                return

            if name in _BLOCK_TAGS:
                # Check that tag is a "leaf-ish" block (no nested block tags)
                nested_blocks = tag.find_all(_BLOCK_TAGS | _HEADING_TAGS)
                if not nested_blocks:
                    text = tag.get_text(separator=" ", strip=True)
                    if is_translatable(text):
                        bid = f"html_{idx}"
                        idx += 1
                        selector = _node_selector(tag)
                        blocks.append(ContentBlock(
                            id=bid,
                            type=BlockType.PARAGRAPH,
                            source_text=text,
                            metadata={"node_path": selector, "attr": None},
                        ))
                        word_count += len(text.split())
                    # Still extract attrs even if text not translatable
                    _extract_attrs(tag, idx)
                    return

            # Translatable attributes on any element
            _extract_attrs(tag, idx)

            for child in tag.children:
                if hasattr(child, "name") and child.name:
                    _visit(child)

        def _extract_attrs(tag, _idx_ref) -> None:
            nonlocal idx
            for attr in _TRANSLATABLE_ATTRS:
                val = (tag.get(attr) or "").strip()
                if val and is_translatable(val):
                    bid = f"html_attr_{idx}"
                    idx += 1
                    selector = _node_selector(tag)
                    blocks.append(ContentBlock(
                        id=bid,
                        type=BlockType.PARAGRAPH,
                        source_text=val,
                        metadata={"node_path": selector, "attr": attr},
                    ))
                    nonlocal word_count
                    word_count += len(val.split())

        body = soup.find("body") or soup
        for child in body.children:
            if hasattr(child, "name") and child.name:
                _visit(child)

        return ParsedFile(
            meta=FileMeta(
                original_name=os.path.basename(file_path),
                file_type=Path(file_path).suffix.lstrip(".").lower(),
                word_count=word_count,
            ),
            blocks=blocks,
            format_template=raw,
        )

    # ------------------------------------------------------------------
    # rebuild
    # ------------------------------------------------------------------
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            raise ImportError("beautifulsoup4 is required for HTML support.") from exc

        raw: str = parsed_file.format_template or ""
        soup = BeautifulSoup(raw, "lxml")

        # Remove skip-tag subtrees
        for skip in soup.find_all(_SKIP_TAGS):
            pass  # Don't decompose — we didn't decompose in parse either

        # Build index: selector → list of matching tags (in document order)
        # We resolve blocks by re-matching their selector
        for block in parsed_file.blocks:
            translated = self._best_text(block)
            if translated == block.source_text:
                continue

            selector = block.metadata.get("node_path", "")
            attr = block.metadata.get("attr")

            if not selector:
                continue

            tag = _find_by_selector(soup, selector)
            if tag is None:
                logger.warning("Could not locate HTML node '%s'", selector)
                continue

            if attr:
                tag[attr] = translated
            else:
                tag.string = translated

        out_text = str(soup)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(out_text, encoding="utf-8")
        logger.info("Rebuilt HTML saved to %s", output_path)
        return output_path


def _find_by_selector(soup, selector: str):
    """Resolve a positional CSS-like selector to a BS4 tag.

    Selector format: ``tag:nth-of-type(n) > tag:nth-of-type(n) > ...``
    """
    parts = [p.strip() for p in selector.split(">")]
    node = soup
    for part in parts:
        if ":nth-of-type(" in part:
            tag_name, rest = part.split(":nth-of-type(", 1)
            n = int(rest.rstrip(")"))
        else:
            tag_name = part
            n = 1

        children = [c for c in node.children if getattr(c, "name", None) == tag_name]
        if n < 1 or n > len(children):
            return None
        node = children[n - 1]

    return node if hasattr(node, "name") and node.name else None
