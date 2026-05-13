"""Paragraph-level text formatting helpers for PPTX parsing and rebuilding."""

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


def write_para_with_fmt(para, text: str, fmt: dict) -> None:
    """Write *text* into *para*'s first non-icon run and apply dominant format.

    Icon-font runs (Material Icons, Font Awesome, Wingdings, …) are left
    completely untouched so their ligature glyphs keep rendering correctly.
    Clears text from other non-icon runs so the paragraph contains exactly
    one text-bearing run plus any preserved icon runs.
    """
    runs = para.runs
    if not runs:
        return  # Paragraph has no runs (rare in PPTX); skip safely.

    runs_kind = fmt.get("runs_kind")
    target_idx = 0
    if runs_kind and len(runs_kind) == len(runs):
        target_idx = next(
            (i for i, k in enumerate(runs_kind) if not k.get("is_icon")),
            -1,
        )
        if target_idx == -1:
            return  # Entire paragraph is icons — nothing translatable to write.

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
        run.text = ""


def distribute_text(
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

    # split translated text into candidate lines
    all_lines = new_text.split("\n")

    if paras_info and len(paras_info) == len(paras):
        # informed path: use stored paragraph structure
        meaningful = [ln for ln in all_lines if ln.strip()]

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
            write_para_with_fmt(para, line, pi)

    else:
        # fallback path: map non-empty source paragraphs to non-empty translation lines.
        # PPTX cells commonly prefix/intersperse content paragraphs with empty
        # <a:p> spacers (only <a:endParaRPr>, no runs). Using para_idx directly
        # against all_lines breaks stride once a spacer is skipped and wipes
        # content paragraphs to "".
        targets = [p for p in paras if p.runs]
        if not targets:
            return
        lines = [ln for ln in all_lines if ln.strip()]
        for i, para in enumerate(targets):
            if i < len(lines) - 1:
                line = lines[i]
            elif i == len(lines) - 1:
                line = "\n".join(lines[i:])
            else:
                line = ""
            para.runs[0].text = line
            for run in para.runs[1:]:
                run.text = ""


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
