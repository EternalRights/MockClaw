"""
MockClaw Resilience Module
Self-healing and error recovery utilities.
"""

from __future__ import annotations

import json
import logging
import os
import signal
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
    """In-memory registry of self-healing patches."""

    patches: list[dict[str, str]] = []

    @classmethod
    def add_patch(cls, error_type: str, fix: str, code: str) -> None:
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
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(cls.patches, f, indent=2)


def retry(
    max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that retries a function with exponential backoff."""

    def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            last_exception: Exception | None = None
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
    """Shut down the agent gracefully, persisting diagnostic data."""
    logger.error(f"FATAL: {reason}")
    ResiliencePatch.save_patches()
    with open("logs/heartbeat.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] | EXIT | Reason: {reason}\n")
    sys.exit(exit_code)


class Watchdog:
    """Timer-based hang detector for long-running agent iterations."""

    def __init__(self, timeout_seconds: int = 600) -> None:
        self.timeout: int = timeout_seconds
        self.last_heartbeat: float = time.time()

    def heartbeat(self) -> None:
        self.last_heartbeat = time.time()

    def check(self) -> bool:
        elapsed = time.time() - self.last_heartbeat
        if elapsed > self.timeout:
            logger.error(f"Watchdog: No heartbeat for {elapsed:.0f}s. Force exit.")
            os._exit(1)
        return elapsed < self.timeout


def setup_signal_handlers() -> None:
    """Register signal handlers for graceful shutdown. Must be called explicitly."""
    def _signal_handler(signum: int, _frame: Any) -> None:
        logger.info(f"Received signal {signum}. Graceful exit...")
        graceful_exit("Signal received", 0)

    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)
