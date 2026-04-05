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
    """In-memory registry of self-healing patches.

    Patches are accumulated across iterations and flushed to disk via
    :meth:`save_patches`.
    """

    patches: list[dict[str, str]] = []

    @classmethod
    def add_patch(cls, error_type: str, fix: str, code: str) -> None:
        """Register a new self-healing patch.

        Args:
            error_type: The type of error that was encountered.
            fix: Description of the fix applied.
            code: Code snippet or TODO comment for the fix.
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
        """Persist registered patches to a JSON file.

        Args:
            path: File path to save patches. Defaults to logs/patches.json.
        """
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, "w", encoding="utf-8") as f:
            json.dump(cls.patches, f, indent=2)


def retry(
    max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0
) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
    """Decorator that retries a function with exponential backoff.

    Args:
        max_retries: Maximum retry attempts (default 3).
        delay: Initial delay in seconds (default 1.0).
        backoff: Multiplier for delay after each attempt (default 2.0).

    Returns:
        A decorator function that wraps the target function with retry logic.
    """

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
            raise last_exception  # unreachable, calms type checker

        return wrapper

    return decorator


def graceful_exit(reason: str, exit_code: int = 1) -> None:
    """Shut down the agent gracefully, persisting diagnostic data.

    Args:
        reason: Human-readable explanation for the exit.
        exit_code: Exit code to return. Defaults to 1 (error).
    """
    logger.error(f"FATAL: {reason}")
    ResiliencePatch.save_patches()
    with open("logs/heartbeat.log", "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] | EXIT | Reason: {reason}\n")
    sys.exit(exit_code)


class Watchdog:
    """Timer-based hang detector for long-running agent iterations."""

    def __init__(self, timeout_seconds: int = 600) -> None:
        """Initialize the watchdog timer.

        Args:
            timeout_seconds: Maximum seconds without heartbeat before
                considering the process hung. Defaults to 600 (10 minutes).
        """
        self.timeout: int = timeout_seconds
        self.last_heartbeat: float = time.time()

    def heartbeat(self) -> None:
        """Record a heartbeat — resets the elapsed timer."""
        self.last_heartbeat = time.time()

    def check(self) -> bool:
        """Check whether the elapsed time is within limits.

        Returns:
            ``True`` if healthy, ``False`` if hung (triggers :func:`os._exit`).
        """
        elapsed = time.time() - self.last_heartbeat
        if elapsed > self.timeout:
            logger.error(f"Watchdog: No heartbeat for {elapsed:.0f}s. Force exit.")
            os._exit(1)
        return elapsed < self.timeout


class ChaosInjector:
    """Inject chaos for testing resilience. Use only in test mode!"""

    @staticmethod
    def kill_docker() -> None:
        """Kill Docker containers randomly."""
        import subprocess

        try:
            result = subprocess.run(
                ["docker", "ps", "-q"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            containers = result.stdout.strip().splitlines()
            if containers:
                container = containers[0]
                subprocess.run(
                    ["docker", "stop", container], timeout=10
                )
                logger.warning(
                    f"Chaos: Killed container {container[:12]}"
                )
        except Exception as e:
            logger.error(f"Chaos injection failed: {e}")

    @staticmethod
    def fill_disk(percent: float = 0.99) -> None:
        """Fill disk to simulate full disk.

        Args:
            percent: Target disk usage percentage. Defaults to 0.99 (99%).
        """
        import shutil

        try:
            total, used, _ = shutil.disk_usage("/")
            target_size = int(total * percent) - used
            if target_size > 0:
                junk = Path("logs/temp/junk.bin")
                junk.parent.mkdir(parents=True, exist_ok=True)
                with open(junk, "wb") as f:
                    f.write(b"\x00" * min(target_size, 100 * 1024 * 1024))
                logger.warning(
                    f"Chaos: Filled disk to {percent * 100:.0f}%"
                )
                junk.unlink(missing_ok=True)
        except Exception as e:
            logger.error(f"Disk fill failed: {e}")

    @staticmethod
    def random_sleep(max_seconds: int = 30) -> None:
        """Random sleep to simulate slow operations.

        Args:
            max_seconds: Maximum sleep duration in seconds. Defaults to 30.
        """
        import random

        delay = random.randint(1, max_seconds)
        logger.warning(f"Chaos: Sleeping for {delay}s")
        time.sleep(delay)


# --------------------------------------------------------------------------


def _signal_handler(signum: int, _frame: Any) -> None:
    """Graceful shutdown handler for SIGTERM / SIGINT."""
    logger.info(f"Received signal {signum}. Graceful exit...")
    graceful_exit("Signal received", 0)


def setup_signal_handlers() -> None:
    """Register signal handlers for graceful shutdown."""
    signal.signal(signal.SIGTERM, _signal_handler)
    signal.signal(signal.SIGINT, _signal_handler)


setup_signal_handlers()
