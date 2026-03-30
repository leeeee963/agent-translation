"""SmartArt / diagram parsing and rebuilding for PPTX files."""

from __future__ import annotations

import logging
import shutil
import zipfile

from lxml import etree

from src.models.content import BlockType, ContentBlock

logger = logging.getLogger(__name__)

_NS_PKG_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS_DML = "http://schemas.openxmlformats.org/drawingml/2006/main"


def build_diagram_map(file_path: str) -> dict[int, str]:
    """Map 1-based slide numbers to diagram data file paths inside the zip."""
    mapping: dict[int, str] = {}
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            for name in z.namelist():
                import re
                m = re.match(r"ppt/slides/_rels/slide(\d+)\.xml\.rels$", name)
                if not m:
                    continue
                slide_num = int(m.group(1))
                rels_xml = z.read(name)
                root = etree.fromstring(rels_xml)
                for rel in root.findall(f"{{{_NS_PKG_RELS}}}Relationship"):
                    target = rel.get("Target", "")
                    if "diagrams/data" in target.lower():
                        dgm_path = target.replace("../", "ppt/")
                        mapping[slide_num] = dgm_path
                        break
    except Exception:
        logger.debug("Could not build diagram map for %s", file_path)
    return mapping


def parse_diagram(
    file_path: str, dgm_data_path: str, slide_idx: int
) -> list[ContentBlock]:
    """Extract text from SmartArt diagram data XML."""
    blocks: list[ContentBlock] = []
    try:
        with zipfile.ZipFile(file_path, "r") as z:
            if dgm_data_path not in z.namelist():
                return blocks
            content = z.read(dgm_data_path)
            root = etree.fromstring(content)

            pts = root.findall(
                ".//{http://schemas.openxmlformats.org/drawingml/2006/diagram}pt"
            )
            item_idx = 0
            for pt in pts:
                texts = pt.findall(f".//{{{_NS_DML}}}t")
                combined = " ".join(
                    (t.text or "").strip() for t in texts
                ).strip()
                if not combined:
                    continue
                blocks.append(
                    ContentBlock(
                        id=f"slide{slide_idx}_dgm{item_idx}",
                        type=BlockType.PARAGRAPH,
                        source_text=combined,
                        metadata={
                            "slide_index": slide_idx,
                            "shape_kind": "diagram",
                            "diagram_data": dgm_data_path,
                            "dgm_item_index": item_idx,
                        },
                    )
                )
                item_idx += 1
    except Exception as e:
        logger.warning("Failed to parse diagram %s: %s", dgm_data_path, e)
    return blocks


def rebuild_diagrams(
    src_pptx: str, dst_pptx: str, block_map: dict[str, ContentBlock]
) -> None:
    """Write translated text back into SmartArt diagram data XML files."""
    dgm_updates: dict[str, list[tuple[int, str]]] = {}
    for block in block_map.values():
        if block.metadata.get("shape_kind") != "diagram":
            continue
        translated = block.reviewed_text or block.translated_text
        if not translated or translated == block.source_text:
            continue
        dgm_path = block.metadata.get("diagram_data", "")
        idx = block.metadata.get("dgm_item_index", -1)
        if dgm_path and idx >= 0:
            dgm_updates.setdefault(dgm_path, []).append((idx, translated))

    if not dgm_updates:
        shutil.move(src_pptx, dst_pptx)
        return

    with zipfile.ZipFile(src_pptx, "r") as zin:
        with zipfile.ZipFile(dst_pptx, "w") as zout:
            for item in zin.infolist():
                data = zin.read(item.filename)
                if item.filename in dgm_updates:
                    data = _patch_diagram_xml(
                        data, dgm_updates[item.filename]
                    )
                zout.writestr(item, data)


def _patch_diagram_xml(
    xml_bytes: bytes, updates: list[tuple[int, str]]
) -> bytes:
    """Replace text in SmartArt diagram data XML by pt-item index."""
    ns_dgm = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
    root = etree.fromstring(xml_bytes)

    pts = root.findall(f".//{{{ns_dgm}}}pt")
    update_map = dict(updates)
    item_idx = 0

    for pt in pts:
        texts = pt.findall(f".//{{{_NS_DML}}}t")
        combined = " ".join((t.text or "").strip() for t in texts).strip()
        if not combined:
            continue
        if item_idx in update_map:
            new_text = update_map[item_idx]
            if texts:
                texts[0].text = new_text
                for extra in texts[1:]:
                    extra.text = ""
        item_idx += 1

    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", standalone=True)
