"""Paragraph-level text formatting helpers for PPTX parsing and rebuilding.

Per-paragraph block model (from 2026-05): each PPTX paragraph that carries
translatable text is its own ContentBlock. The LLM returns one [[BLOCK:id]]
per paragraph, so newline-based splitting heuristics are gone — rebuild looks
up the translation by (text_frame_group, para_index) and writes it directly.
"""

from __future__ import annotations

import logging

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


def get_para_dominant_fmt(para) -> dict:
    """Analyse all runs in *para* and return the dominant character format.

    "Dominant" means the format covers >= 40% of the paragraph's characters.
    Only *explicitly* set run attributes (True/False, not None=inherited) are
    considered — None means "inherit from theme/master" and is left untouched.

    Returns a dict with keys: text, translatable_text, runs_kind,
                               bold, italic, underline,
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

    runs_kind: list[dict] = []
    translatable_parts: list[str] = []
    for run in para.runs:
        is_icon = _run_is_icon(run)
        runs_kind.append({"is_icon": is_icon, "text": run.text})
        if not is_icon:
            translatable_parts.append(run.text)
    translatable_text = "".join(translatable_parts)

    thresh = max(total_chars * 0.4, 0.5)
    return {
        "text": para.text,
        "translatable_text": translatable_text,
        "runs_kind": runs_kind,
        "bold": (bold_chars >= thresh) if any_explicit_bold else None,
        "italic": (italic_chars >= thresh) if any_explicit_italic else None,
        "underline": (underline_chars >= thresh) if any_explicit_underline else None,
        "font_name": font_name,
        "font_size": font_size,   # raw EMU value, or None
        "color": color,
    }


def write_para_with_fmt(para, text: str, fmt: dict | None) -> None:
    """Write *text* into *para*'s first non-icon run and apply dominant format.

    Icon-font runs (Material Icons, Font Awesome, Wingdings, …) are left
    completely untouched so their ligature glyphs keep rendering correctly.
    Clears text from other non-icon runs so the paragraph contains exactly
    one text-bearing run plus any preserved icon runs.

    *text* may not contain newlines — caller must collapse any \\n / \\r first
    (per-paragraph blocks are single-line by contract).
    """
    runs = para.runs
    if not runs:
        return  # Paragraph has no runs (rare in PPTX); skip safely.

    fmt = fmt or {}
    runs_kind = fmt.get("runs_kind")
    target_idx = 0
    if runs_kind and len(runs_kind) == len(runs):
        target_idx = next(
            (i for i, k in enumerate(runs_kind) if not k.get("is_icon")),
            -1,
        )
        if target_idx == -1:
            return  # Entire paragraph is icons — nothing translatable to write.
    else:
        # Fallback: pick the first non-icon run by inspecting the run itself.
        target_idx = next(
            (i for i, r in enumerate(runs) if not _run_is_icon(r)),
            -1,
        )
        if target_idx == -1:
            return

    target = runs[target_idx]
    target.text = text

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
        if runs_kind and i < len(runs_kind) and runs_kind[i].get("is_icon"):
            continue  # Preserve icon-font run as-is.
        if not runs_kind and _run_is_icon(run):
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
    paras_blocks: dict[int, "object"],
) -> tuple[str, str]:
    """Write per-paragraph translations into *text_frame*.

    *paras_blocks* maps paragraph-index → ContentBlock for paragraphs that had
    translatable content at parse time. Paragraphs absent from the map are
    spacers or icon-only — we leave them untouched.

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
        block = paras_blocks.get(para_idx)
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
        # Re-apply any leading/trailing whitespace that surrounded the
        # translatable text in the source paragraph (e.g., the space after
        # an icon-font ligature).
        candidate = (meta.get("lead_ws") or "") + candidate + (meta.get("trail_ws") or "")
        para_format = meta.get("para_format") or {}
        write_para_with_fmt(para, candidate, para_format)
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
