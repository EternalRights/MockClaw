"""
MockClaw Resilience Module
Self-healing and error recovery utilities for the Immortal Agent.
"""

import os
import sys
import time
import signal
import logging
import traceback
from functools import wraps
from typing import Callable, Any, Optional
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s',
    handlers=[
        logging.FileHandler('logs/agent.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger('MockClaw')


class ResiliencePatch:
    """Track and apply self-healing patches."""
    patches = []
    
    @classmethod
    def add_patch(cls, error_type: str, fix: str, code: str):
        cls.patches.append({
            'error': error_type,
            'fix': fix,
            'code': code,
            'timestamp': datetime.now().isoformat()
        })
        logger.info(f"Patch registered: {fix}")
    
    @classmethod
    def save_patches(cls, path: str = 'logs/patches.json'):
        import json
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cls.patches, f, indent=2)


def retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Retry decorator with exponential backoff."""
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
                        logger.warning(f"Attempt {attempt + 1}/{max_retries + 1} failed: {e}. Retry in {current_delay:.1f}s")
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        ResiliencePatch.add_patch(
                            error_type=type(e).__name__,
                            fix=f"Add retry for {type(e).__name__}",
                            code=f"# TODO: Handle {type(e).__name__}"
                        )
                        raise
            raise last_exception
        return wrapper
    return decorator


def graceful_exit(reason: str, exit_code: int = 1):
    """Graceful exit with patch logging."""
    logger.error(f"FATAL: {reason}")
    ResiliencePatch.save_patches()
    with open('logs/heartbeat.log', 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().isoformat()}] | EXIT | Reason: {reason}\n")
    sys.exit(exit_code)


class Watchdog:
    """Watchdog timer to detect hung processes."""
    def __init__(self, timeout_seconds: int = 600):
        self.timeout = timeout_seconds
        self.last_heartbeat = time.time()
    
    def heartbeat(self):
        self.last_heartbeat = time.time()
    
    def check(self) -> bool:
        elapsed = time.time() - self.last_heartbeat
        if elapsed > self.timeout:
            logger.error(f"Watchdog: No heartbeat for {elapsed:.0f}s. Force exit.")
            os._exit(1)
        return elapsed < self.timeout
