"""Centralized path resolution for both development and PyInstaller-bundled modes.

When running from source, all paths resolve to the project root.
When frozen (PyInstaller .app), immutable assets come from the bundle,
while mutable user data lives in ~/Library/Application Support/AgentTranslation/.
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path


def is_frozen() -> bool:
    return getattr(sys, "frozen", False)


def get_bundle_dir() -> Path:
    """Root of bundled (read-only) resources."""
    if is_frozen():
        return Path(sys._MEIPASS)  # type: ignore[attr-defined]
    return Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    """Root of mutable user data. Writable across launches."""
    if is_frozen():
        d = Path.home() / "Library" / "Application Support" / "AgentTranslation"
        d.mkdir(parents=True, exist_ok=True)
        return d
    return Path(__file__).resolve().parents[2]


def get_config_dir() -> Path:
    """Writable config directory (copy of bundled defaults on first launch)."""
    return get_data_dir() / "config"


def get_frontend_dist_dir() -> Path:
    """Frontend static files — always from the bundle (read-only)."""
    return get_bundle_dir() / "frontend" / "dist"


def initialize_user_data() -> None:
    """Copy default config and data scaffolding from the bundle to the user data dir.

    Only copies files that do not already exist, preserving user edits.
    Called once at desktop app startup.
    """
    if not is_frozen():
        return

    bundle = get_bundle_dir()
    data = get_data_dir()

    # Seed config/ (prompts, styles, languages, settings.yaml)
    _seed_dir(bundle / "config", data / "config")

    # Ensure data/ subdirectories exist
    (data / "data").mkdir(parents=True, exist_ok=True)
    (data / "data" / "cache" / "llm").mkdir(parents=True, exist_ok=True)


def _seed_dir(src: Path, dst: Path) -> None:
    """Recursively copy files from *src* to *dst*, skipping existing files."""
    if not src.is_dir():
        return
    dst.mkdir(parents=True, exist_ok=True)
    for item in src.rglob("*"):
        if item.is_file():
            target = dst / item.relative_to(src)
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(item, target)
