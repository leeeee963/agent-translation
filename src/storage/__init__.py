"""Pluggable file storage. Switch backends via STORAGE_BACKEND env var."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from src.storage.base import FileStorage
from src.storage.local import LocalStorage
from src.storage.s3 import S3Storage
from src.utils.paths import get_data_dir

logger = logging.getLogger(__name__)

_storage: FileStorage | None = None


def get_storage() -> FileStorage:
    global _storage
    if _storage is not None:
        return _storage

    backend = os.getenv("STORAGE_BACKEND", "local").strip().lower()

    if backend == "s3":
        bucket = os.getenv("S3_BUCKET", "").strip()
        if not bucket:
            raise RuntimeError("STORAGE_BACKEND=s3 but S3_BUCKET is not set")
        _storage = S3Storage(
            bucket=bucket,
            endpoint_url=os.getenv("S3_ENDPOINT_URL"),
            access_key=os.getenv("S3_ACCESS_KEY"),
            secret_key=os.getenv("S3_SECRET_KEY"),
            region=os.getenv("S3_REGION", "us-east-1"),
        )
        logger.info("Storage backend: s3 (bucket=%s)", bucket)
    else:
        root_env = os.getenv("STORAGE_LOCAL_ROOT", "").strip()
        root_path = Path(root_env) if root_env else (get_data_dir() / "data" / "storage")
        _storage = LocalStorage(root=root_path)
        logger.info("Storage backend: local (root=%s)", root_path)

    return _storage


def reset_storage() -> None:
    """For tests / lifespan shutdown."""
    global _storage
    _storage = None


__all__ = ["FileStorage", "LocalStorage", "S3Storage", "get_storage", "reset_storage"]
