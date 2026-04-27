"""
MockClaw LLM Client Manager
Manages LLM client initialization, caching, and lazy loading.
"""

from __future__ import annotations

import os
from typing import Any

OPENAI_AVAILABLE = False


class LLMClientManager:
    """Manages LLM client lifecycle with lazy loading and caching.

    Defers the expensive OpenAI import (~800ms) until the first call to
    ``get_client()``.  Subsequent calls return the cached instance.

    Args:
        api_key: Optional API key. Falls back to LLM_API_KEY then
                 OPENAI_API_KEY env vars.
        base_url: Optional base URL for the API endpoint.
    """

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self._api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv(
            "OPENAI_API_KEY"
        )
        self._base_url = base_url or os.getenv("LLM_BASE_URL")
        self._client: Any = None
        self._initialized: bool = False

    def get_client(self) -> Any:
        """Return a cached OpenAI client, creating one on first call.

        Returns:
            An ``OpenAI`` instance, or ``None`` when the library is not
            installed or no API key is configured.
        """
        if self._initialized:
            return self._client

        self._initialized = True
        global OPENAI_AVAILABLE

        try:
            from openai import OpenAI

            OPENAI_AVAILABLE = True
        except ImportError:
            OPENAI_AVAILABLE = False
            return None

        if not self._api_key:
            return None

        try:
            kwargs: dict[str, Any] = {"api_key": self._api_key}
            if self._base_url:
                kwargs["base_url"] = self._base_url
            self._client = OpenAI(**kwargs)
        except Exception:
            self._client = None

        return self._client

    @property
    def is_available(self) -> bool:
        """Check whether an LLM client can be provided."""
        if not self._initialized:
            return bool(self._api_key)
        return self._client is not None
