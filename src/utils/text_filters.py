"""Shared text-filtering utilities used by multiple parsers."""
from __future__ import annotations

import re

_URL_RE = re.compile(r"^https?://\S+$|^www\.\S+$", re.IGNORECASE)
_NUM_ONLY_RE = re.compile(r"^[\d\s.,;:+\-*/=%$€£¥()[\]{}]+$")
# Placeholder patterns: {name}, %s, %1$s, {{var}}, ${var}
_PLACEHOLDER_RE = re.compile(
    r"\{[^{}]*\}|%\d*\$?[sdfouxX]|%[sdfouxX]|\{\{[^{}]+\}\}|\$\{[^{}]+\}"
)


def is_translatable(text: str) -> bool:
    """Return False for content that should not be translated."""
    t = text.strip()
    if not t:
        return False
    if len(t) < 2:
        return False
    if _URL_RE.match(t):
        return False
    if _NUM_ONLY_RE.match(t):
        return False
    return True


def extract_placeholders(text: str) -> list[str]:
    """Return all placeholder tokens found in *text* (e.g. ``{name}``, ``%s``)."""
    return _PLACEHOLDER_RE.findall(text)
