"""Style loader: scans config/styles/ for YAML files, assembles prompt text.

Architecture:
    config/styles/
        formal.yaml       ← built-in styles (shipped with the project)
        technical.yaml
        _template.yaml     ← ignored (starts with _)
        ...

    Users add/edit files in this directory directly.
    File name (without .yaml) becomes the style key used in --style flag.

Design decisions:
    - Each style is a standalone YAML file → easy to add/copy/share.
    - build_style_prompt() assembles whatever fields exist into prompt text.
      Unknown fields are included as-is, so adding new fields (tone, audience,
      register, etc.) requires NO code changes — just edit the YAML.
    - The _SECTION_RENDERERS dict controls how known fields are formatted.
      Everything else goes through a generic renderer.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)

_CONFIG_DIR = Path(__file__).resolve().parents[2] / "config"
_STYLES_DIR = _CONFIG_DIR / "styles"

_SKIP_IN_PROMPT = {"name", "description", "prompt_name", "prompt_description"}


def _render_guidelines(value: str) -> str:
    return f"Guidelines:\n{value.strip()}"


def _render_examples(value: list[dict[str, str]]) -> str:
    lines = ["Examples:"]
    for i, ex in enumerate(value, 1):
        lines.append(f"  Example {i}:")
        if "source" in ex:
            lines.append(f"    Source: {ex['source']}")
        if "target" in ex:
            lines.append(f"    Target: {ex['target']}")
        if "note" in ex:
            lines.append(f"    Note: {ex['note']}")
    return "\n".join(lines)


def _render_avoid(value: list[str]) -> str:
    lines = ["Avoid:"]
    for item in value:
        lines.append(f"  - {item}")
    return "\n".join(lines)


def _render_generic(key: str, value: Any) -> str:
    """Render an unknown field as-is — makes the system pluggable."""
    if isinstance(value, list):
        items = "\n".join(f"  - {v}" for v in value)
        return f"{key}:\n{items}"
    if isinstance(value, str):
        return f"{key}: {value.strip()}"
    return f"{key}: {value}"


_SECTION_RENDERERS: dict[str, Any] = {
    "guidelines": _render_guidelines,
    "examples": _render_examples,
    "avoid": _render_avoid,
}


def _load_style_file(path: Path) -> dict[str, Any]:
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    return data


def list_styles() -> dict[str, dict[str, Any]]:
    """Return {key: config_dict} for all available styles."""
    if not _STYLES_DIR.is_dir():
        logger.warning("Styles directory not found: %s", _STYLES_DIR)
        return {}

    styles: dict[str, dict[str, Any]] = {}
    for p in sorted(_STYLES_DIR.glob("*.yaml")):
        if p.name.startswith("_"):
            continue
        key = p.stem
        try:
            styles[key] = _load_style_file(p)
        except Exception:
            logger.warning("Failed to load style file: %s", p, exc_info=True)
    return styles


def get_style(key: str) -> dict[str, Any]:
    """Load a single style by key. Returns empty dict if not found."""
    path = _STYLES_DIR / f"{key}.yaml"
    if not path.exists():
        logger.warning("Style '%s' not found at %s", key, path)
        return {}
    return _load_style_file(path)


def build_style_prompt(key: str) -> str:
    """Build rich prompt text from a style's YAML config.

    Assembles all fields into structured prompt text.
    Unknown fields are rendered generically — no code change needed to add them.
    """
    cfg = get_style(key)
    if not cfg:
        return ""

    sections: list[str] = []

    name = cfg.get("prompt_name", cfg.get("name", key))
    desc = cfg.get("prompt_description", cfg.get("description", ""))
    header = f"Style: {name}"
    if desc:
        header += f" ({desc})"
    sections.append(header)

    for field, value in cfg.items():
        if field in _SKIP_IN_PROMPT or value is None:
            continue

        renderer = _SECTION_RENDERERS.get(field)
        if renderer:
            sections.append(renderer(value))
        else:
            sections.append(_render_generic(field, value))

    return "\n\n".join(sections)


def get_style_file_path(key: str) -> Path:
    """Return the file path for a given style key."""
    return _STYLES_DIR / f"{key}.yaml"


def save_style(key: str, config: dict[str, Any]) -> Path:
    """Save a style config to a YAML file. Returns the path written."""
    path = get_style_file_path(key)
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(
            config,
            f,
            allow_unicode=True,
            default_flow_style=False,
            sort_keys=False,
        )
    logger.info("Saved style '%s' to %s", key, path)
    return path
