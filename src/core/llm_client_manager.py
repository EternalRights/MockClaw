"""
MockClaw LLM Client Manager
Manages LLM client initialization, caching, lazy loading, and retry logic.
"""

from __future__ import annotations

import os
import time
import logging
from typing import Any

_logger = logging.getLogger(__name__)


class LLMClientManager:
    """Manages LLM client lifecycle with lazy loading, caching, and retries.

    Defers the expensive OpenAI import (~800ms) until the first call to
    ``get_client()``.  Subsequent calls return the cached instance.

    Args:
        api_key: Optional API key. Falls back to LLM_API_KEY then
                 OPENAI_API_KEY env vars.
        base_url: Optional base URL for the API endpoint.
        max_retries: Maximum number of retry attempts for transient errors.
        retry_delay: Base delay in seconds between retries (exponential backoff).
        request_timeout: Timeout in seconds for each API request.
    """

    _TRANSIENT_ERRORS = (
        ConnectionError,
        TimeoutError,
        OSError,
    )

    def __init__(
        self,
        api_key: str | None = None,
        base_url: str | None = None,
        max_retries: int = 3,
        retry_delay: float = 1.0,
        request_timeout: float = 60.0,
    ) -> None:
        self._api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv(
            "OPENAI_API_KEY"
        )
        self._base_url = base_url or os.getenv("LLM_BASE_URL")
        self._client: Any = None
        self._initialized: bool = False
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._request_timeout = request_timeout

    def get_client(self) -> Any:
        """Return a cached OpenAI client, creating one on first call.

        Returns:
            An ``OpenAI`` instance, or ``None`` when the library is not
            installed or no API key is configured.
        """
        if self._initialized:
            return self._client

        self._initialized = True

        try:
            from openai import OpenAI
        except ImportError:
            return None

        if not self._api_key:
            return None

        try:
            kwargs: dict[str, Any] = {
                "api_key": self._api_key,
                "timeout": self._request_timeout,
                "max_retries": 0,
            }
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

    @property
    def max_retries(self) -> int:
        return self._max_retries

    @property
    def retry_delay(self) -> float:
        return self._retry_delay

    def call_with_retry(self, fn, *args, **kwargs) -> Any:
        """Execute an LLM API call with exponential backoff retry.

        Args:
            fn: Callable that performs the API call (e.g., client.chat.completions.create).
            *args: Positional arguments forwarded to *fn*.
            **kwargs: Keyword arguments forwarded to *fn*.

        Returns:
            The result of the successful API call.

        Raises:
            The last exception if all retries are exhausted.
        """
        model = kwargs.get("model", "unknown")
        last_exc: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                result = fn(*args, **kwargs)
                if attempt > 0:
                    _logger.info("LLM call succeeded on attempt %d/%d (model=%s)", attempt + 1, self._max_retries, model)
                else:
                    _logger.debug("LLM call succeeded (model=%s)", model)
                return result
            except self._TRANSIENT_ERRORS as exc:
                last_exc = exc
                if attempt < self._max_retries - 1:
                    delay = self._retry_delay * (2 ** attempt)
                    _logger.warning(
                        "LLM call failed (attempt %d/%d), retrying in %.1fs: %s",
                        attempt + 1,
                        self._max_retries,
                        delay,
                        exc,
                    )
                    time.sleep(delay)
            except Exception:
                raise
        raise last_exc  # type: ignore[misc]
