"""Centralized path resolution — all paths resolve relative to the project root."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[2]


def get_data_dir() -> Path:
    """Project root directory."""
    return _ROOT


def get_config_dir() -> Path:
    """Config directory."""
    return _ROOT / "config"


def get_frontend_dist_dir() -> Path:
    """Frontend static files."""
    return _ROOT / "frontend" / "dist"
