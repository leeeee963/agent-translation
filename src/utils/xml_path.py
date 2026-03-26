"""Utilities for generating and resolving positional paths for lxml / BS4 nodes.

Used by XML and HTML parsers to record where a node lives in the tree so
the rebuild step can locate it without re-parsing the whole document.

Path format (lxml)
------------------
Each segment is  ``tag[n]``  where *n* is the 1-based element index among
siblings with the same tag.  Segments are joined with ``/``.

Example::

    /root/body[1]/p[2]
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lxml.etree import _Element  # noqa: F401


def lxml_node_path(element) -> str:
    """Return a stable positional path string for an lxml *element*."""
    parts: list[str] = []
    node = element
    while node is not None and node.tag is not None:
        parent = node.getparent()
        if parent is None:
            parts.append(node.tag if isinstance(node.tag, str) else "root")
            break
        siblings = [c for c in parent if c.tag == node.tag]
        idx = siblings.index(node) + 1  # 1-based
        tag = node.tag if isinstance(node.tag, str) else "node"
        # Strip namespace from tag for readability
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        parts.append(f"{tag}[{idx}]")
        node = parent
    parts.reverse()
    return "/" + "/".join(parts)


def lxml_find_by_path(root, path: str):
    """Locate an lxml element by the path produced by :func:`lxml_node_path`.

    Returns the element or ``None`` if not found.
    """
    parts = [p for p in path.strip("/").split("/") if p]
    node = root
    # The first part is the root tag itself; skip if it matches root
    start = 0
    first_tag = parts[0].split("[")[0] if parts else ""
    root_tag = root.tag.split("}")[-1] if isinstance(root.tag, str) and "}" in root.tag else (root.tag or "")
    if first_tag == root_tag or first_tag == "root":
        start = 1

    for part in parts[start:]:
        if "[" in part:
            tag, rest = part.split("[", 1)
            idx = int(rest.rstrip("]")) - 1  # 0-based
        else:
            tag, idx = part, 0

        children = [c for c in node if (
            c.tag == tag
            or (isinstance(c.tag, str) and c.tag.split("}")[-1] == tag)
        )]
        if idx >= len(children):
            return None
        node = children[idx]

    return node
