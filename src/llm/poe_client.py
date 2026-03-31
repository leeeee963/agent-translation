"""Poe API client for calling ChatGPT-4o.

Poe provides an OpenAI-compatible API at https://api.poe.com/v1.
Configure via environment variable POE_API_KEY or config/settings.yaml.
Get your API key at: https://poe.com/api/keys
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
from pathlib import Path
from typing import Any

import httpx
import yaml

logger = logging.getLogger(__name__)


def _load_config() -> dict[str, Any]:
    from src.utils.paths import get_config_dir
    cfg_path = get_config_dir() / "settings.yaml"
    if cfg_path.exists():
        with open(cfg_path, encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    return {}


class PoeClient:
    """Async wrapper around Poe's OpenAI-compatible API."""

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str = "https://api.poe.com/v1",
        timeout: int = 120,
        max_retries: int = 3,
        retry_delay: float = 2.0,
    ):
        cfg = _load_config()
        poe_cfg = cfg.get("poe", {})
        self.api_key = api_key or os.getenv("POE_API_KEY") or poe_cfg.get("api_key", "")
        self.base_url = base_url or poe_cfg.get("base_url", "https://api.poe.com/v1")
        self.timeout = timeout or poe_cfg.get("timeout", 120)
        self.max_retries = max_retries or poe_cfg.get("max_retries", 3)
        self.retry_delay = retry_delay or poe_cfg.get("retry_delay", 2.0)
        self._models: dict[str, str] = cfg.get("models", {})
        self._default_model = "GPT-4o"
        self._http_client: httpx.AsyncClient | None = None
        cache_cfg = cfg.get("llm_cache", {})
        self._cache_enabled = bool(cache_cfg.get("enabled", True))
        cache_dir = cache_cfg.get("dir", "data/cache/llm")
        from src.utils.paths import get_data_dir
        self._cache_dir = get_data_dir() / cache_dir
        if self._cache_enabled:
            self._cache_dir.mkdir(parents=True, exist_ok=True)

        if not self.api_key or self.api_key == "${POE_API_KEY}":
            logger.warning(
                "POE_API_KEY not set. Get your key at https://poe.com/api/keys "
                "then: export POE_API_KEY='your_key'"
            )

    def _get_http_client(self) -> httpx.AsyncClient:
        """Return a shared httpx client for connection pooling."""
        if self._http_client is None or self._http_client.is_closed:
            self._http_client = httpx.AsyncClient(timeout=self.timeout)
        return self._http_client

    def get_model(self, task: str) -> str:
        """Get the configured model for a task (terminology/translation/review/etc)."""
        return self._models.get(task, self._default_model)

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.3,
        model: str | None = None,
    ) -> str:
        """Send a chat-completion request and return the assistant reply.

        Uses the OpenAI-compatible endpoint: POST /v1/chat/completions
        """
        payload = {
            "model": model or self._default_model,
            "messages": messages,
            "temperature": temperature,
        }
        cache_key = self._build_cache_key(payload)
        cached = self._load_cached_response(cache_key)
        if cached is not None:
            logger.debug("LLM cache hit: %s", cache_key)
            return cached

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}/chat/completions"

        last_error: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                client = self._get_http_client()
                resp = await client.post(url, headers=headers, json=payload)
                resp.raise_for_status()
                data = resp.json()
                reply = self._extract_reply(data)
                self._save_cached_response(cache_key, reply)
                return reply
            except (httpx.HTTPStatusError, httpx.RequestError, KeyError) as exc:
                last_error = exc
                wait = self.retry_delay * (2 ** (attempt - 1))
                logger.warning(
                    "Poe API call failed (attempt %d/%d): %s  — retrying in %.1fs",
                    attempt, self.max_retries, exc, wait,
                )
                await asyncio.sleep(wait)

        raise RuntimeError(
            f"Poe API call failed after {self.max_retries} retries: {last_error}"
        )

    async def simple_chat(
        self,
        user_message: str,
        system_message: str = "",
        temperature: float = 0.3,
        model: str | None = None,
    ) -> str:
        """Convenience wrapper: single user message with optional system prompt."""
        messages: list[dict[str, str]] = []
        if system_message:
            messages.append({"role": "system", "content": system_message})
        messages.append({"role": "user", "content": user_message})
        return await self.chat(messages, temperature=temperature, model=model)

    @staticmethod
    def _extract_reply(data: Any) -> str:
        """Extract the assistant text from OpenAI-compatible response."""
        if isinstance(data, dict):
            choices = data.get("choices")
            if choices and isinstance(choices, list):
                msg = choices[0].get("message", {})
                content = msg.get("content", "")
                if content:
                    return content

        raise KeyError(f"Cannot extract reply from response: {json.dumps(data)[:300]}")

    def _build_cache_key(self, payload: dict[str, Any]) -> str:
        text = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _cache_path(self, cache_key: str) -> Path:
        return self._cache_dir / f"{cache_key}.json"

    def _load_cached_response(self, cache_key: str) -> str | None:
        if not self._cache_enabled:
            return None
        path = self._cache_path(cache_key)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                reply = data.get("reply")
                if isinstance(reply, str):
                    return reply
        except (OSError, json.JSONDecodeError):
            logger.warning("Failed to read LLM cache: %s", path)
        return None

    def _save_cached_response(self, cache_key: str, reply: str) -> None:
        if not self._cache_enabled:
            return
        path = self._cache_path(cache_key)
        try:
            path.write_text(
                json.dumps({"reply": reply}, ensure_ascii=False),
                encoding="utf-8",
            )
        except OSError:
            logger.warning("Failed to write LLM cache: %s", path)


def get_client() -> PoeClient:
    """Return a PoeClient that reads the latest settings.yaml on every call.

    Intentionally not cached: this ensures that model / key changes in
    settings.yaml take effect for the next job without a server restart.
    Connection pooling still works within a single PoeClient instance
    (the httpx.AsyncClient is lazy-created and reused per instance).
    """
    return PoeClient()
