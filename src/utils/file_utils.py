from __future__ import annotations

import os
import tempfile
from pathlib import Path


def get_temp_dir() -> Path:
    d = Path(tempfile.gettempdir()) / "agent_translation"
    d.mkdir(parents=True, exist_ok=True)
    return d


def ensure_output_path(source_path: str, target_language: str) -> str:
    p = Path(source_path)
    stem = p.stem
    suffix = p.suffix
    output_name = f"{stem}_{target_language}{suffix}"
    return str(p.parent / output_name)


def validate_file(path: str, supported_extensions: list[str] | None = None) -> None:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在: {path}")
    if not p.is_file():
        raise ValueError(f"路径不是文件: {path}")

    max_size_mb = int(os.getenv("MAX_FILE_SIZE_MB", "50"))
    size_mb = p.stat().st_size / (1024 * 1024)
    if size_mb > max_size_mb:
        raise ValueError(f"文件过大: {size_mb:.1f}MB（限制 {max_size_mb}MB）")

    if supported_extensions:
        if p.suffix.lower() not in supported_extensions:
            raise ValueError(
                f"不支持的文件格式: {p.suffix}\n"
                f"当前支持: {', '.join(supported_extensions)}"
            )


def get_file_type(path: str) -> str:
    return Path(path).suffix.lower().lstrip(".")
