from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

LANGUAGE_NAMES = {
    "zh-cn": "中文（简体）", "zh-tw": "中文（繁体）",
    "en": "English", "ja": "日本語", "ko": "한국어",
    "mn": "Монгол", "th": "ไทย", "vi": "Tiếng Việt",
    "id": "Bahasa Indonesia", "kk": "Қазақ",
    "fr": "Français", "de": "Deutsch", "es": "Español",
    "pt": "Português", "ru": "Русский",
}

# English names for use in LLM prompts (ensures the model understands the language)
LANGUAGE_NAMES_EN = {
    "zh-cn": "Simplified Chinese", "zh-tw": "Traditional Chinese",
    "en": "English", "ja": "Japanese", "ko": "Korean",
    "mn": "Mongolian", "th": "Thai", "vi": "Vietnamese",
    "id": "Indonesian", "kk": "Kazakh",
    "fr": "French", "de": "German", "es": "Spanish",
    "pt": "Portuguese", "ru": "Russian",
}


def detect_language(text: str) -> str:
    """Detect language of the given text, returning a language code."""
    if not text.strip():
        return "en"
    try:
        from langdetect import detect
        raw = detect(text)
    except Exception:
        logger.warning("langdetect failed, defaulting to 'en'")
        return "en"

    mapping = {"zh-cn": "zh-CN", "zh-tw": "zh-TW", "zh": "zh-CN"}
    return mapping.get(raw, raw)


def get_language_name(code: str) -> str:
    return LANGUAGE_NAMES.get(code.lower(), code)
