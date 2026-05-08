from __future__ import annotations

import re

# Trailing characters to strip from the end of each subtitle line.
# Includes ASCII punctuation, CJK punctuation, ellipsis chars, en/em dashes,
# and whitespace. Closing quotes, closing brackets, and the ASCII hyphen are
# intentionally excluded.
_TRAILING_RE = re.compile(r"[\s,.!?;:，。！？；：、…⋯—–]+$")


def strip_line_end_punctuation(text: str) -> str:
    """Strip trailing punctuation/whitespace from each line of subtitle text.

    Operates on each newline-separated line independently so multi-line cues
    are cleaned line-by-line. If stripping a line would leave it empty (the
    line was entirely punctuation), the original line is preserved so cues
    are never silently blanked out.
    """
    out: list[str] = []
    for line in text.split("\n"):
        stripped = _TRAILING_RE.sub("", line)
        out.append(stripped if stripped else line)
    return "\n".join(out)
