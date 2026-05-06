"""Local filesystem storage. Default for development."""

from __future__ import annotations

import shutil
from pathlib import Path
from urllib.parse import quote

from src.storage.base import FileStorage


class LocalStorage(FileStorage):
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        # Block path traversal — keys should never contain ".."
        clean = key.replace("..", "").lstrip("/")
        return self.root / clean

    def upload_file(self, key: str, source_path: Path) -> None:
        target = self._path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(source_path, target)

    def download_to_path(self, key: str, target_path: Path) -> None:
        src = self._path(key)
        if not src.exists():
            raise FileNotFoundError(f"Storage key not found: {key}")
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(src, target_path)

    def exists(self, key: str) -> bool:
        return self._path(key).is_file()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists() and p.is_file():
            p.unlink()

    def delete_prefix(self, prefix: str) -> int:
        target = self._path(prefix)
        count = 0
        if target.is_dir():
            for f in target.rglob("*"):
                if f.is_file():
                    f.unlink()
                    count += 1
            shutil.rmtree(target, ignore_errors=True)
        elif target.is_file():
            target.unlink()
            count = 1
        return count

    def get_url(
        self, key: str, filename: str | None = None, expires_in: int = 3600
    ) -> str:
        return f"/api/storage/{quote(key)}"

    def is_redirect_url(self) -> bool:
        return False

    def local_path(self, key: str) -> Path:
        """Direct filesystem path — only valid for LocalStorage."""
        return self._path(key)
