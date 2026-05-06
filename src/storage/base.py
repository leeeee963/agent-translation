"""FileStorage abstract interface.

A pluggable file backend used for uploaded source files and translation
products. Two implementations: LocalStorage (filesystem) and S3Storage
(any S3-compatible service: AWS S3, Cloudflare R2, Backblaze B2, etc.).
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path


class FileStorage(ABC):
    @abstractmethod
    def upload_file(self, key: str, source_path: Path) -> None:
        """Copy a local file into storage under the given key."""

    @abstractmethod
    def download_to_path(self, key: str, target_path: Path) -> None:
        """Materialize the stored object back to a local file."""

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def delete_prefix(self, prefix: str) -> int:
        """Delete all keys starting with prefix. Returns count deleted."""

    @abstractmethod
    def get_url(
        self, key: str, filename: str | None = None, expires_in: int = 3600
    ) -> str:
        """Return a URL the client can use to download.

        - LocalStorage returns a relative path served by the FastAPI app.
        - S3Storage returns a presigned URL (valid for `expires_in` seconds).
        """

    @abstractmethod
    def is_redirect_url(self) -> bool:
        """If True, downloads should HTTP-redirect to get_url(). Else, stream."""
