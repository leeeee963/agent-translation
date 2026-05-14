"""Paragraph-level text formatting helpers for PPTX parsing and rebuilding.

Per-soft-line block model (revised 2026-05): each PPTX *visual line* is its
own ContentBlock. A "visual line" is bounded by:
  • the start/end of a <a:p> paragraph,
  • a literal "\\n" inside an <a:t> run text (PowerPoint stores a soft line
    break this way), or
  • an <a:br/> element between runs.

The block id encodes both the paragraph and the soft-line within it:
``slide{N}_shape{M}_p{K}_l{L}``. The LLM returns one [[BLOCK:id]] per soft
line, so a header + bullet packed into one <a:p> via soft break gets two
separate markers — no more silent content reshuffle when the LLM gets
confused by multi-line block content.
"""

from __future__ import annotations

import logging

from lxml import etree

logger = logging.getLogger(__name__)


_A_NS = "http://schemas.openxmlformats.org/drawingml/2006/main"

# Icon fonts render literal strings like "check_circle" as ligature glyphs.
# We must NOT send these to the LLM (it would translate "check_circle" as a word)
# and must NOT write translations back into them (icon fonts have no CJK glyphs,
# so the translated text renders as broken boxes or wrong-style fallback).
_ICON_FONT_PATTERNS = (
    "material icons",
    "material symbols",
    "font awesome",
    "fontawesome",
    "wingdings",
    "webdings",
    "segoe mdl2",
    "segoe fluent",
    "bootstrap icons",
    "phosphor",
    "ionicons",
    "lucide",
)


def _is_icon_font(typeface: str | None) -> bool:
    if not typeface:
        return False
    lower = typeface.lower()
    return any(p in lower for p in _ICON_FONT_PATTERNS)


def _run_is_icon(run) -> bool:
    try:
        if _is_icon_font(run.font.name):
            return True
    except Exception:
        pass
    rpr = run._r.find(f"{{{_A_NS}}}rPr")
    if rpr is not None:
        for kind in ("latin", "ea", "cs", "sym"):
            el = rpr.find(f"{{{_A_NS}}}{kind}")
            if el is not None and _is_icon_font(el.get("typeface")):
                return True
    return False


def split_para_into_soft_lines(para) -> list[dict]:
    """Split a paragraph into visual lines.

    Boundaries: a literal ``\\n`` at the end of a run's text, an ``<a:br/>``
    element between runs, or the paragraph itself starting/ending.

    Returns a list of line dicts in document order:
      ``{"runs": [Run, ...], "trailing_break": "newline" | "br" | None}``

    A line with no runs (empty soft-line, e.g., consecutive ``<a:br/>``) is
    still emitted so para-rebuild can preserve the visual gap.
    """
    run_map = {r._r: r for r in para.runs}

    lines: list[dict] = []
    current: dict = {"runs": [], "trailing_break": None}

    for child in para._p:
        tag = etree.QName(child.tag).localname
        if tag == "r":
            run = run_map.get(child)
            if run is None:
                continue
            current["runs"].append(run)
            text = run.text or ""
            if text.endswith("\n"):
                # The soft break lives at the end of this run's text.
                current["trailing_break"] = "newline"
                lines.append(current)
                current = {"runs": [], "trailing_break": None}
            elif "\n" in text:
                # Mid-run \n: rare but possible. We don't currently split a
                # single <a:r> across two soft lines because that would
                # require restructuring the XML. Log so we know if we hit it.
                logger.warning(
                    "Mid-run \\n encountered in paragraph; soft-line "
                    "splitting may be coarse for this paragraph."
                )
        elif tag == "br":
            current["trailing_break"] = "br"
            lines.append(current)
            current = {"runs": [], "trailing_break": None}

    if current["runs"] or not lines:
        lines.append(current)

    return lines


def _line_translatable_text(line: dict) -> str:
    """Concatenate non-icon-run text for a soft line, stripping the trailing
    ``\\n`` from the last run if that's where the soft break lives."""
    runs = line["runs"]
    parts: list[str] = []
    for i, run in enumerate(runs):
        if _run_is_icon(run):
            continue
        text = run.text or ""
        if i == len(runs) - 1 and line["trailing_break"] == "newline":
            text = text.rstrip("\n")
        parts.append(text)
    return "".join(parts)


def _line_dominant_fmt(line: dict) -> dict:
    """Return the dominant character format for one soft line.

    Uses the same >= 40% threshold as the previous per-paragraph helper but
    scoped to runs of this line. Also records ``runs_kind`` so the rebuild
    knows which runs are icon-fonts (preserve) vs. text (overwrite).
    """
    runs = line["runs"]

    total_chars = 0
    bold_chars = italic_chars = underline_chars = 0
    any_explicit_bold = any_explicit_italic = any_explicit_underline = False
    font_name: str | None = None
    font_size: int | None = None
    color: str | None = None

    for i, run in enumerate(runs):
        text = run.text or ""
        if i == len(runs) - 1 and line["trailing_break"] == "newline":
            text = text.rstrip("\n")
        n = len(text)
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
            font_size = run.font.size
        if color is None:
            try:
                if run.font.color and run.font.color.type is not None:
                    color = str(run.font.color.rgb)
            except (AttributeError, TypeError):
                pass

    runs_kind: list[dict] = []
    for i, run in enumerate(runs):
        text = run.text or ""
        if i == len(runs) - 1 and line["trailing_break"] == "newline":
            text = text.rstrip("\n")
        runs_kind.append({"is_icon": _run_is_icon(run), "text": text})

    thresh = max(total_chars * 0.4, 0.5)
    return {
        "translatable_text": _line_translatable_text(line),
        "runs_kind": runs_kind,
        "bold": (bold_chars >= thresh) if any_explicit_bold else None,
        "italic": (italic_chars >= thresh) if any_explicit_italic else None,
        "underline": (underline_chars >= thresh) if any_explicit_underline else None,
        "font_name": font_name,
        "font_size": font_size,
        "color": color,
        "trailing_break": line["trailing_break"],
    }


def _write_soft_line(line: dict, line_format: dict | None, text: str) -> None:
    """Write *text* into the first non-icon run of *line*; clear other non-icon
    runs in the same line; preserve icon-font runs and re-apply the line's
    trailing soft break (``\\n`` appended to the written text, or the existing
    ``<a:br/>`` element which we don't touch).

    *text* must be single-line (caller flattens any LLM-injected newlines).
    """
    runs = line["runs"]
    if not runs:
        return

    target_idx = next(
        (i for i, r in enumerate(runs) if not _run_is_icon(r)),
        -1,
    )
    if target_idx == -1:
        return  # Line is all icons — nothing translatable to overwrite.

    target = runs[target_idx]
    text_to_write = text
    if line["trailing_break"] == "newline":
        text_to_write = text_to_write + "\n"
    target.text = text_to_write

    fmt = line_format or {}
    bold = fmt.get("bold")
    italic = fmt.get("italic")
    underline = fmt.get("underline")
    if bold is not None:
        target.font.bold = bold
    if italic is not None:
        target.font.italic = italic
    if underline is not None:
        target.font.underline = underline

    for i, run in enumerate(runs):
        if i == target_idx:
            continue
        if _run_is_icon(run):
            continue
        run.text = ""


def _flatten_for_paragraph(text: str) -> str:
    """Collapse newlines/CR for single-paragraph writing.

    LLM occasionally returns multi-line output for a per-paragraph block. PPTX
    runs render literal \\n as nothing or a stray glyph depending on viewer, so
    we replace with a single space and squash repeats.
    """
    if not text:
        return ""
    flat = text.replace("\r\n", " ").replace("\r", " ").replace("\n", " ")
    while "  " in flat:
        flat = flat.replace("  ", " ")
    return flat.strip()


def write_paragraphs_by_index(
    text_frame,
    paras_blocks: dict[tuple[int, int], "object"],
) -> tuple[str, str]:
    """Write per-soft-line translations into *text_frame*.

    *paras_blocks* maps ``(para_index, line_index)`` → ContentBlock for every
    soft line that had translatable content at parse time. Lines absent from
    the map are spacers or icon-only — we leave them untouched.

    Translation precedence: ``reviewed_text`` then ``translated_text``. If both
    are empty we fall back to ``source_text`` so a missing translation never
    blanks a cell, and emit a warning so the gap is visible in logs.

    Returns ``(joined_source, joined_translated)`` for downstream font-size
    autofit calculations. Empty strings if nothing was written.
    """
    paras = list(text_frame.paragraphs)
    source_chunks: list[str] = []
    translated_chunks: list[str] = []

    for para_idx, para in enumerate(paras):
        soft_lines = split_para_into_soft_lines(para)
        for line_idx, line in enumerate(soft_lines):
            block = paras_blocks.get((para_idx, line_idx))
            if block is None:
                continue
            preferred = (
                (block.reviewed_text or "").strip()
                or (block.translated_text or "").strip()
            )
            if preferred:
                candidate = _flatten_for_paragraph(preferred)
            else:
                logger.warning(
                    "Block %s: no translation produced; falling back to source text",
                    getattr(block, "id", "?"),
                )
                candidate = _flatten_for_paragraph(block.source_text)
            if not candidate:
                continue
            meta = block.metadata or {}
            candidate = (meta.get("lead_ws") or "") + candidate + (meta.get("trail_ws") or "")
            line_format = meta.get("line_format") or {}
            _write_soft_line(line, line_format, candidate)
            source_chunks.append(block.source_text)
            translated_chunks.append(candidate)

    return "\n".join(source_chunks), "\n".join(translated_chunks)


def warn_overflow(source: str, translated: str, block_id: str) -> None:
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
