"""
MockClaw Resilience Module
===========================

Self-healing and error recovery utilities for the Immortal Agent.

Provides:
- :class:`ResiliencePatch` — Tracks and persists self-healing patches.
- :func:`retry` — Decorator for automatic retries with exponential backoff.
- :func:`graceful_exit` — Controlled shutdown with diagnostic logging.
- :class:`Watchdog` — Timer-based hang detection for long-running operations.

The module configures a shared ``logger`` instance that writes to both
``logs/agent.log`` and stdout, so every component in the Immortal Agent
can use ``from core.resilience import logger`` for consistent formatting.
"""

import json
import logging
import os
import sys
import time
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Any, Callable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    handlers=[
        logging.FileHandler("logs/agent.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("MockClaw")


class ResiliencePatch:
    """In-memory registry of self-healing patches.

    Each patch records an error type, a human-readable fix description,
    and a stub code snippet.  Patches are accumulated across iterations
    and flushed to disk via :meth:`save_patches`.

    Attributes:
        patches: Class-level list of patch dictionaries accumulated
                 during the current agent lifetime.
    """

    patches: list[dict[str, str]] = []

    @classmethod
    def add_patch(cls, error_type: str, fix: str, code: str) -> None:
        """Register a new self-healing patch.

        Args:
            error_type: The exception class name or category that triggered the patch.
            fix: Human-readable description of the proposed fix.
            code: Stub or placeholder code for the fix.
        """
        cls.patches.append(
            {
                "error": error_type,
                "fix": fix,
                "code": code,
                "timestamp": datetime.now().isoformat(),
            }
        )
        logger.info(f"Patch registered: {fix}")

    @classmethod
    def save_patches(cls, path: str = "logs/patches.json") -> None:
        """Persist all registered patches to a JSON file.

        Creates parent directories if they do not exist.

        Args:
            path: Destination file path (default: ``logs/patches.json``).
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(cls.patches, f, indent=2)


def retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator that retries a function on failure with exponential backoff.

    On each failed attempt the delay is multiplied by *backoff*.
    If all retries are exhausted, a :class:`ResiliencePatch` is registered
    and the last exception is re-raised.

    Args:
        max_retries: Maximum number of retry attempts (default ``3``).
        delay: Initial delay in seconds between retries (default ``1.0``).
        backoff: Multiplier applied to the delay after each attempt (default ``2.0``).

    Returns:
        A decorator wrapping the target function.

    Example::

        @retry(max_retries=5, delay=0.5, backoff=1.5)
        def flaky_network_call():
            ...
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            last_exception = None
            current_delay = delay
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        logger.warning(
                            f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. "
                            f"Retry in {current_delay:.1f}s"
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        ResiliencePatch.add_patch(
                            error_type=type(e).__name__,
                            fix=f"Add retry for {type(e).__name__}",
                            code=f"# TODO: Handle {type(e).__name__}",
                        )
                        raise
            raise last_exception

        return wrapper

    return decorator


def graceful_exit(reason: str, exit_code: int = 1) -> None:
    """Shut down the agent gracefully, persisting diagnostic data.

    Saves all registered resilience patches and appends an exit record
    to ``logs/heartbeat.log`` before calling :func:`sys.exit`.

    Args:
        reason: Human-readable explanation for the shutdown.
        exit_code: Process exit code (default ``1`` — failure).
    """
    logger.error(f"FATAL: {reason}")
    ResiliencePatch.save_patches()
    with open("logs/heartbeat.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] | EXIT | Reason: {reason}\n")
    sys.exit(exit_code)


class Watchdog:
    """Timer-based hang detector for long-running agent iterations.

    The watchdog records the time of the last :meth:`heartbeat` call.
    :meth:`check` compares the elapsed time against the configured timeout
    and force-kills the process if it has been exceeded.

    Args:
        timeout_seconds: Maximum allowed interval between heartbeats
                         before the process is killed (default ``600``).

    Note:
        Uses :func:`os._exit` instead of :func:`sys.exit` to bypass
        Python's cleanup handlers — appropriate for an unrecoverable hang.
    """

    def __init__(self, timeout_seconds: int = 600) -> None:
        self.timeout: int = timeout_seconds
        self.last_heartbeat: float = time.time()

    def heartbeat(self) -> None:
        """Record a heartbeat — resets the elapsed timer."""
        self.last_heartbeat = time.time()

    def check(self) -> bool:
        """Check whether the elapsed time since the last heartbeat is within limits.

        Returns:
            ``True`` if the watchdog is healthy (within timeout),
            ``False`` if the process is hung (triggers :func:`os._exit`).
        """
        elapsed = time.time() - self.last_heartbeat
        if elapsed > self.timeout:
            logger.error(f"Watchdog: No heartbeat for {elapsed:.0f}s. Force exit.")
            os._exit(1)
        return elapsed < self.timeout
