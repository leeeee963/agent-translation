"""PPTX parser: handles text frames, tables, grouped shapes, and SmartArt.

Recursively processes GroupShapes and extracts SmartArt diagram text
from the PPTX package's diagram data files.

Format-fidelity design:
- Each text frame is stored with per-paragraph info (text + dominant format).
- On rebuild, translated text is split by \\n and written back paragraph-by-
  paragraph, so bullet points stay as separate bullets.
- Per-paragraph dominant format (bold/italic/underline) is re-applied on the
  translated run, so formatting is preserved even when the run boundaries
  change during translation.
"""

from __future__ import annotations

import logging
import os
import re
import shutil
import uuid
import zipfile
from pathlib import Path

from lxml import etree
from pptx import Presentation
from pptx.util import Pt

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser
from src.utils.layout_fixer import adjust_runs_font_size, enable_autofit

logger = logging.getLogger(__name__)

_HEADING_FONT_SIZE_THRESHOLD = Pt(24)

_NS_PKG_RELS = "http://schemas.openxmlformats.org/package/2006/relationships"
_NS_DML = "http://schemas.openxmlformats.org/drawingml/2006/main"


# ── Paragraph-level format helpers ───────────────────────────────────────────

def _get_para_dominant_fmt(para) -> dict:
    """Analyse all runs in *para* and return the dominant character format.

    "Dominant" means the format covers ≥ 40 % of the paragraph's characters.
    Only *explicitly* set run attributes (True/False, not None=inherited) are
    considered — None means "inherit from theme/master" and is left untouched.

    Returns a dict with keys: text, bold, italic, underline,
                               font_name, font_size (EMU int), color.
    """
    total_chars = 0
    bold_chars = italic_chars = underline_chars = 0
    any_explicit_bold = any_explicit_italic = any_explicit_underline = False
    font_name: str | None = None
    font_size: int | None = None
    color: str | None = None

    for run in para.runs:
        n = len(run.text)
        total_chars += n

        if run.font.bold is True:
            bold_chars += n
            any_explicit_bold = True
        elif run.font.bold is False:
            any_explicit_bold = True

        if run.font.italic is True:
            italic_chars += n
            any_explicit_italic = True
        elif run.font.italic is False:
            any_explicit_italic = True

        if run.font.underline is True:
            underline_chars += n
            any_explicit_underline = True
        elif run.font.underline is False:
            any_explicit_underline = True

        if font_name is None and run.font.name:
            font_name = run.font.name
        if font_size is None and run.font.size:
            font_size = run.font.size  # EMU integer
        if color is None:
            try:
                if run.font.color and run.font.color.type is not None:
                    color = str(run.font.color.rgb)
            except (AttributeError, TypeError):
                pass

    thresh = max(total_chars * 0.4, 0.5)
    return {
        "text": para.text,
        "bold": (bold_chars >= thresh) if any_explicit_bold else None,
        "italic": (italic_chars >= thresh) if any_explicit_italic else None,
        "underline": (underline_chars >= thresh) if any_explicit_underline else None,
        "font_name": font_name,
        "font_size": font_size,   # raw EMU value, or None
        "color": color,
    }


def _write_para_with_fmt(para, text: str, fmt: dict) -> None:
    """Write *text* into *para*'s first run and apply dominant format.

    Clears all subsequent runs so the paragraph contains exactly one run
    with the translated text.  Only overrides bold/italic/underline when
    they were explicitly set in the original paragraph.
    """
    runs = para.runs
    if not runs:
        return  # Paragraph has no runs (rare in PPTX); skip safely.

    first = runs[0]
    first.text = text

    bold = fmt.get("bold")
    italic = fmt.get("italic")
    underline = fmt.get("underline")
    if bold is not None:
        first.font.bold = bold
    if italic is not None:
        first.font.italic = italic
    if underline is not None:
        first.font.underline = underline

    for run in runs[1:]:
        run.text = ""


class PptxParser(BaseParser):
    """Parser for Microsoft PowerPoint (.pptx) files."""

    EXTENSIONS = {".pptx"}

    def can_handle(self, file_path: str) -> bool:
        return Path(file_path).suffix.lower() in self.EXTENSIONS

    # ------------------------------------------------------------------
    # parse
    # ------------------------------------------------------------------
    def parse(self, file_path: str) -> ParsedFile:
        prs = Presentation(file_path)
        blocks: list[ContentBlock] = []
        total_words = 0

        diagram_map = self._build_diagram_map(file_path)

        for slide_idx, slide in enumerate(prs.slides):
            slide_blocks = self._parse_shape_tree(slide.shapes, slide_idx)
            blocks.extend(slide_blocks)

            slide_num = slide_idx + 1
            if slide_num in diagram_map:
                dgm_blocks = self._parse_diagram(
                    file_path, diagram_map[slide_num], slide_idx
                )
                blocks.extend(dgm_blocks)

            if slide.has_notes_slide:
                notes_tf = slide.notes_slide.notes_text_frame
                notes_text = notes_tf.text.strip()
                if notes_text:
                    total_words += len(notes_text.split())
                    blocks.append(
                        ContentBlock(
                            id=f"slide{slide_idx}_note",
                            type=BlockType.SLIDE_NOTE,
                            source_text=notes_text,
                            metadata={"slide_index": slide_idx},
                        )
                    )

        total_words += sum(
            len(b.source_text.split())
            for b in blocks
            if b.type != BlockType.SLIDE_NOTE
        )

        return ParsedFile(
            meta=FileMeta(
                original_name=os.path.basename(file_path),
                file_type="pptx",
                word_count=total_words,
            ),
            blocks=blocks,
            format_template=str(Path(file_path).resolve()),
        )

    # ── SmartArt / diagram handling ──────────────────────────────────

    @staticmethod
    def _build_diagram_map(file_path: str) -> dict[int, str]:
        """Map 1-based slide numbers to diagram data file paths inside the zip."""
        mapping: dict[int, str] = {}
        try:
            with zipfile.ZipFile(file_path, "r") as z:
                for name in z.namelist():
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

    @staticmethod
    def _parse_diagram(
        file_path: str, dgm_data_path: str, slide_idx: int
    ) -> list[ContentBlock]:
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

    # ── shape tree (text frames, tables, groups) ─────────────────────

    def _parse_shape_tree(
        self, shapes, slide_idx: int, prefix: str = ""
    ) -> list[ContentBlock]:
        blocks: list[ContentBlock] = []
        for shape_idx, shape in enumerate(shapes):
            shape_id = (
                f"{prefix}shape{shape_idx}" if prefix else f"shape{shape_idx}"
            )
            block_id_base = f"slide{slide_idx}_{shape_id}"
            blocks_before = len(blocks)

            # GroupShape — recurse
            if shape.shape_type is not None and shape.shape_type == 6:
                try:
                    blocks.extend(
                        self._parse_shape_tree(
                            shape.shapes, slide_idx, prefix=f"{shape_id}_"
                        )
                    )
                except Exception:
                    logger.debug("Could not iterate group shape %s", block_id_base)
                continue

            # Chart — extract title, categories, series names
            if hasattr(shape, "has_chart") and shape.has_chart:
                chart_blocks = self._parse_chart(shape.chart, slide_idx, block_id_base)
                blocks.extend(chart_blocks)

            # Table
            if shape.has_table:
                blocks.extend(
                    self._parse_table(shape.table, slide_idx, block_id_base)
                )

            # Text frame
            if shape.has_text_frame:
                block = self._parse_text_frame(
                    shape.text_frame, slide_idx, shape_idx, block_id_base
                )
                if block:
                    blocks.append(block)
            elif not shape.has_table and not (hasattr(shape, "has_chart") and shape.has_chart):
                # Fallback: try to get text from shapes without text_frame
                try:
                    text = shape.text.strip() if hasattr(shape, "text") else ""
                    if text:
                        blocks.append(
                            ContentBlock(
                                id=block_id_base,
                                type=BlockType.PARAGRAPH,
                                source_text=text,
                                metadata={
                                    "slide_index": slide_idx,
                                    "shape_index": shape_idx,
                                    "shape_kind": "fallback_text",
                                },
                            )
                        )
                except Exception:
                    pass

            if len(blocks) == blocks_before:
                logger.debug(
                    "Shape %s (type=%s) produced no content blocks",
                    block_id_base,
                    getattr(shape, "shape_type", "unknown"),
                )

        return blocks

    def _parse_text_frame(
        self, tf, slide_idx: int, shape_idx: int, block_id: str
    ) -> ContentBlock | None:
        full_text = tf.text.strip()
        if not full_text:
            return None

        # Collect per-paragraph info: text + dominant format.
        # This drives both the bullet-point distribution and format restoration
        # during rebuild.
        paras_info = [_get_para_dominant_fmt(para) for para in tf.paragraphs]

        # Determine block type from the largest font size found.
        max_font_size = 0
        for pi in paras_info:
            fs = pi.get("font_size")
            if fs and fs > max_font_size:
                max_font_size = fs

        block_type = (
            BlockType.HEADING
            if max_font_size >= _HEADING_FONT_SIZE_THRESHOLD
            else BlockType.PARAGRAPH
        )

        return ContentBlock(
            id=block_id,
            type=block_type,
            source_text=full_text,
            style={"paras": paras_info},
            metadata={
                "slide_index": slide_idx,
                "shape_index": shape_idx,
                "paras_info": paras_info,
                "shape_kind": "text_frame",
            },
        )

    def _parse_table(
        self, table, slide_idx: int, block_id_base: str
    ) -> list[ContentBlock]:
        blocks: list[ContentBlock] = []
        for row_idx, row in enumerate(table.rows):
            for col_idx, cell in enumerate(row.cells):
                text = cell.text.strip()
                if not text:
                    continue
                cell_id = f"{block_id_base}_r{row_idx}c{col_idx}"
                blocks.append(
                    ContentBlock(
                        id=cell_id,
                        type=BlockType.PARAGRAPH,
                        source_text=text,
                        metadata={
                            "slide_index": slide_idx,
                            "table_block": block_id_base,
                            "row": row_idx,
                            "col": col_idx,
                            "shape_kind": "table_cell",
                        },
                    )
                )
        return blocks

    def _parse_chart(
        self, chart, slide_idx: int, block_id_base: str
    ) -> list[ContentBlock]:
        """Extract translatable text from chart: title, category labels, series names."""
        blocks: list[ContentBlock] = []

        # Chart title
        try:
            if chart.has_title and chart.chart_title.has_text_frame:
                title_text = chart.chart_title.text_frame.text.strip()
                if title_text:
                    blocks.append(
                        ContentBlock(
                            id=f"{block_id_base}_chart_title",
                            type=BlockType.HEADING,
                            source_text=title_text,
                            metadata={
                                "slide_index": slide_idx,
                                "shape_kind": "chart_title",
                            },
                        )
                    )
        except Exception:
            logger.debug("Could not extract chart title from %s", block_id_base)

        # Category axis labels
        try:
            plot = chart.plots[0]
            categories = [str(cat) for cat in plot.categories if str(cat).strip()]
            if categories:
                cat_text = " | ".join(categories)
                blocks.append(
                    ContentBlock(
                        id=f"{block_id_base}_chart_cats",
                        type=BlockType.PARAGRAPH,
                        source_text=cat_text,
                        metadata={
                            "slide_index": slide_idx,
                            "shape_kind": "chart_categories",
                            "category_count": len(categories),
                        },
                    )
                )
        except Exception:
            logger.debug("Could not extract chart categories from %s", block_id_base)

        # Series names
        try:
            for s_idx, series in enumerate(chart.series):
                try:
                    name = series.name if hasattr(series, "name") else None
                    if name and str(name).strip():
                        blocks.append(
                            ContentBlock(
                                id=f"{block_id_base}_chart_s{s_idx}",
                                type=BlockType.PARAGRAPH,
                                source_text=str(name).strip(),
                                metadata={
                                    "slide_index": slide_idx,
                                    "shape_kind": "chart_series",
                                    "series_index": s_idx,
                                },
                            )
                        )
                except Exception:
                    pass
        except Exception:
            logger.debug("Could not extract chart series from %s", block_id_base)

        return blocks

    # ------------------------------------------------------------------
    # rebuild
    # ------------------------------------------------------------------
    def rebuild(self, parsed_file: ParsedFile, output_path: str) -> str:
        original_path = parsed_file.format_template
        if not original_path or not os.path.exists(original_path):
            raise FileNotFoundError(
                f"Original PPTX not found: {original_path}"
            )

        tmp_path = f"{output_path}.tmp_{uuid.uuid4().hex[:8]}.pptx"
        shutil.copy2(original_path, tmp_path)
        prs = Presentation(tmp_path)

        block_map = self._build_block_map(parsed_file)

        for slide_idx, slide in enumerate(prs.slides):
            self._rebuild_shape_tree(slide.shapes, slide_idx, block_map)
            self._rebuild_notes(slide, slide_idx, block_map)

        prs.save(tmp_path)

        diagram_blocks = [
            b for b in parsed_file.blocks
            if b.metadata.get("shape_kind") == "diagram"
        ]
        if diagram_blocks:
            self._rebuild_diagrams(tmp_path, output_path, block_map)
        else:
            shutil.move(tmp_path, output_path)

        if os.path.exists(tmp_path):
            os.remove(tmp_path)

        logger.info("Rebuilt PPTX saved to %s", output_path)
        return output_path

    @staticmethod
    def _build_block_map(parsed_file: ParsedFile) -> dict[str, ContentBlock]:
        return {b.id: b for b in parsed_file.blocks}

    def _rebuild_shape_tree(
        self,
        shapes,
        slide_idx: int,
        block_map: dict[str, ContentBlock],
        prefix: str = "",
    ) -> None:
        for shape_idx, shape in enumerate(shapes):
            shape_id = (
                f"{prefix}shape{shape_idx}" if prefix else f"shape{shape_idx}"
            )
            block_id_base = f"slide{slide_idx}_{shape_id}"

            if shape.shape_type is not None and shape.shape_type == 6:
                try:
                    self._rebuild_shape_tree(
                        shape.shapes, slide_idx, block_map,
                        prefix=f"{shape_id}_",
                    )
                except Exception:
                    pass
                continue

            # Chart
            if hasattr(shape, "has_chart") and shape.has_chart:
                self._rebuild_chart(shape.chart, block_id_base, block_map)

            if shape.has_table:
                self._rebuild_table(shape.table, block_id_base, block_map)

            if shape.has_text_frame:
                block = block_map.get(block_id_base)
                if block is None:
                    continue
                translated = self._best_text(block)
                if not translated or translated == block.source_text:
                    continue
                self._warn_overflow(block.source_text, translated, block_id_base)
                paras_info = block.metadata.get("paras_info")
                self._distribute_text(shape.text_frame, translated, paras_info)
                enable_autofit(shape.text_frame)
                adjust_runs_font_size(shape.text_frame, block.source_text, translated)

    def _rebuild_chart(
        self, chart, block_id_base: str, block_map: dict[str, ContentBlock]
    ) -> None:
        """Write translated text back into chart elements."""
        title_block = block_map.get(f"{block_id_base}_chart_title")
        if title_block:
            translated = self._best_text(title_block)
            if translated and translated != title_block.source_text:
                try:
                    if chart.has_title and chart.chart_title.has_text_frame:
                        self._distribute_text(chart.chart_title.text_frame, translated)
                except Exception:
                    logger.debug("Could not rebuild chart title %s", block_id_base)

        cats_block = block_map.get(f"{block_id_base}_chart_cats")
        if cats_block:
            translated = self._best_text(cats_block)
            if translated and translated != cats_block.source_text:
                logger.info(
                    "Chart category labels translated but chart data source "
                    "may need manual update: %s", block_id_base
                )

    def _rebuild_table(
        self, table, block_id_base: str, block_map: dict[str, ContentBlock]
    ) -> None:
        for row_idx, row in enumerate(table.rows):
            for col_idx, cell in enumerate(row.cells):
                cell_id = f"{block_id_base}_r{row_idx}c{col_idx}"
                block = block_map.get(cell_id)
                if block is None:
                    continue
                translated = self._best_text(block)
                if not translated or translated == block.source_text:
                    continue
                self._distribute_text(cell.text_frame, translated)
                enable_autofit(cell.text_frame)
                adjust_runs_font_size(cell.text_frame, block.source_text, translated)

    @staticmethod
    def _rebuild_diagrams(
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

    def _rebuild_notes(
        self, slide, slide_idx: int, block_map: dict[str, ContentBlock]
    ) -> None:
        block_id = f"slide{slide_idx}_note"
        block = block_map.get(block_id)
        if block is None:
            return
        if not slide.has_notes_slide:
            return
        translated = self._best_text(block)
        if not translated or translated == block.source_text:
            return
        notes_tf = slide.notes_slide.notes_text_frame
        self._distribute_text(notes_tf, translated)

    @staticmethod
    def _distribute_text(
        text_frame,
        new_text: str,
        paras_info: list | None = None,
    ) -> None:
        """Distribute *new_text* back across the paragraphs of *text_frame*.

        Strategy
        --------
        1. Split *new_text* on ``\\n`` to get per-paragraph translated lines.
        2. Only write to paragraphs that were non-empty in the original
           (tracked via *paras_info*).  Originally-empty paragraphs (used for
           spacing) are cleared and left empty so the layout is preserved.
        3. Apply the dominant bold/italic/underline from the original paragraph
           to the translated run, so formatting is faithfully restored.

        When *paras_info* is ``None`` (table cells, chart titles, notes) the
        method falls back to a simple newline-split across paragraphs without
        any format re-application.
        """
        paras = text_frame.paragraphs
        if not paras:
            return

        # ── split translated text into candidate lines ────────────────
        all_lines = new_text.split("\n")

        if paras_info and len(paras_info) == len(paras):
            # ── informed path: use stored paragraph structure ─────────
            # Collect only lines that have actual content (the LLM may not
            # reproduce every blank separator line).
            meaningful = [ln for ln in all_lines if ln.strip()]

            # Map meaningful lines to the originally non-empty paragraphs.
            non_empty_idx = [
                i for i, p in enumerate(paras_info)
                if p.get("text", "").strip()
            ]

            trans_ptr = 0
            for para_idx, para in enumerate(paras):
                pi = paras_info[para_idx]
                if not pi.get("text", "").strip():
                    # Originally empty paragraph (spacer) — keep it empty.
                    for run in para.runs:
                        run.text = ""
                    continue

                line = meaningful[trans_ptr] if trans_ptr < len(meaningful) else ""
                trans_ptr += 1
                _write_para_with_fmt(para, line, pi)

        else:
            # ── fallback path: simple positional split ────────────────
            # Write one line per paragraph; extra lines are appended to the
            # last paragraph.  No format re-application.
            for para_idx, para in enumerate(paras):
                if not para.runs:
                    continue
                if para_idx < len(all_lines) - 1:
                    line = all_lines[para_idx]
                elif para_idx == len(all_lines) - 1:
                    # Last (or only) line: consume all remaining lines.
                    line = "\n".join(all_lines[para_idx:])
                else:
                    line = ""
                para.runs[0].text = line
                for run in para.runs[1:]:
                    run.text = ""

    @staticmethod
    def _warn_overflow(source: str, translated: str, block_id: str) -> None:
        if len(source) == 0:
            return
        ratio = len(translated) / len(source)
        if ratio > 1.5:
            logger.warning(
                "Block %s: translated text is %.1fx longer than source – "
                "may overflow the shape.",
                block_id,
                ratio,
            )


def _patch_diagram_xml(
    xml_bytes: bytes, updates: list[tuple[int, str]]
) -> bytes:
    """Replace text in SmartArt diagram data XML by pt-item index."""
    root = etree.fromstring(xml_bytes)
    ns_dgm = "http://schemas.openxmlformats.org/drawingml/2006/diagram"

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
