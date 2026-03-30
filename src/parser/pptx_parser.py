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
import shutil
import uuid
from pathlib import Path

from pptx import Presentation
from pptx.util import Pt

from src.models.content import BlockType, ContentBlock, FileMeta, ParsedFile
from src.parser.base import BaseParser
from src.parser.pptx_diagram import build_diagram_map, parse_diagram, rebuild_diagrams
from src.parser.pptx_text import (
    get_para_dominant_fmt,
    distribute_text,
    warn_overflow,
)
from src.utils.layout_fixer import adjust_runs_font_size, enable_autofit

logger = logging.getLogger(__name__)

_HEADING_FONT_SIZE_THRESHOLD = Pt(24)


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

        diagram_map = build_diagram_map(file_path)

        for slide_idx, slide in enumerate(prs.slides):
            slide_blocks = self._parse_shape_tree(slide.shapes, slide_idx)
            blocks.extend(slide_blocks)

            slide_num = slide_idx + 1
            if slide_num in diagram_map:
                dgm_blocks = parse_diagram(
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

        paras_info = [get_para_dominant_fmt(para) for para in tf.paragraphs]

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
            rebuild_diagrams(tmp_path, output_path, block_map)
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
                warn_overflow(block.source_text, translated, block_id_base)
                paras_info = block.metadata.get("paras_info")
                distribute_text(shape.text_frame, translated, paras_info)
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
                        distribute_text(chart.chart_title.text_frame, translated)
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
                distribute_text(cell.text_frame, translated)
                enable_autofit(cell.text_frame)
                adjust_runs_font_size(cell.text_frame, block.source_text, translated)

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
        distribute_text(notes_tf, translated)
