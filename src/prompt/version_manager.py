"""Track prompt versions and their quality scores for rollback capability."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_STORE_PATH = Path(__file__).resolve().parents[2] / "data" / "prompt_versions.json"


class PromptVersion(BaseModel):
    version_id: str = ""
    prompt_name: str = ""
    content_hash: str = ""
    created_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    scores: dict[str, float] = Field(default_factory=dict)
    notes: str = ""


class PromptVersionManager:
    """Persists prompt version history with quality scores."""

    def __init__(self, store_path: str | Path | None = None) -> None:
        self._path = Path(store_path) if store_path else _STORE_PATH
        self._versions: dict[str, list[dict[str, Any]]] = self._load()

    def _load(self) -> dict[str, list[dict[str, Any]]]:
        if self._path.exists():
            try:
                return json.loads(self._path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                logger.warning("Corrupt prompt version store; starting fresh.")
        return {}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(
            json.dumps(self._versions, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def record(self, prompt_name: str, content: str, notes: str = "") -> str:
        import hashlib

        content_hash = hashlib.sha256(content.encode()).hexdigest()[:12]
        history = self._versions.setdefault(prompt_name, [])

        if history and history[-1].get("content_hash") == content_hash:
            return history[-1]["version_id"]

        version_id = f"{prompt_name}_v{len(history) + 1}"
        entry = PromptVersion(
            version_id=version_id,
            prompt_name=prompt_name,
            content_hash=content_hash,
            notes=notes,
        )
        history.append(entry.model_dump())
        self._save()
        logger.info("Recorded prompt version %s", version_id)
        return version_id

    def record_score(
        self, prompt_name: str, test_id: str, score: float
    ) -> None:
        history = self._versions.get(prompt_name, [])
        if not history:
            return
        latest = history[-1]
        latest.setdefault("scores", {})[test_id] = score
        self._save()

    def get_latest(self, prompt_name: str) -> PromptVersion | None:
        history = self._versions.get(prompt_name, [])
        if not history:
            return None
        return PromptVersion(**history[-1])

    def get_history(self, prompt_name: str) -> list[PromptVersion]:
        return [
            PromptVersion(**v) for v in self._versions.get(prompt_name, [])
        ]
