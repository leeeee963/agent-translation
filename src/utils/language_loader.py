"""Loader for language-specific structural notes used in the naturalness review pass."""

from __future__ import annotations

from pathlib import Path

import yaml

from src.utils.paths import get_config_dir

_NOTES_PATH = get_config_dir() / "languages" / "structural_notes.yaml"

_cache: dict[str, str] | None = None


def _load_all() -> dict[str, str]:
    global _cache
    if _cache is not None:
        return _cache
    try:
        raw = yaml.safe_load(_NOTES_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        raw = {}
    _cache = {code: entry.get("notes", "").strip() for code, entry in raw.items() if isinstance(entry, dict)}
    return _cache


def get_structural_notes(language_code: str) -> str:
    """Return language-specific structural notes for the given language code, or empty string."""
    notes = _load_all().get(language_code.lower(), "")
    if notes:
        return f"Language-specific rules for {language_code}:\n{notes}"
    return ""
