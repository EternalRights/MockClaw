"""
MockClaw Resilience Module
Self-healing and error recovery utilities.
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

# Configure logging
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
        """Register a patch for a specific error."""
        cls.patches.append({
            'error': error_type,
            'fix': fix,
            'code': code,
            'timestamp': datetime.now().isoformat()
        })
        logger.info(f"Patch registered: {fix}")
        
    @classmethod
    def save_patches(cls, path: str = 'logs/patches.json'):
        """Save patches to file."""
        import json
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(cls.patches, f, indent=2)
        logger.info(f"Saved {len(cls.patches)} patches to {path}")


def retry(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    Retry decorator with exponential backoff.
    
    Args:
        max_retries: Maximum retry attempts
        delay: Initial delay between retries
        backoff: Multiplier for delay after each retry
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
                            f"Retrying in {current_delay:.1f}s..."
                        )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(f"All retries exhausted for {func.__name__}")
                        
                        # Register patch for this error
                        ResiliencePatch.add_patch(
                            error_type=type(e).__name__,
                            fix=f"Increase retries or add specific handling for {type(e).__name__}",
                            code=f"# TODO: Handle {type(e).__name__} gracefully"
                        )
                        raise
            raise last_exception
        return wrapper
    return decorator


def graceful_exit(reason: str, exit_code: int = 1):
    """
    Graceful exit with patch logging.
    
    Args:
        reason: Why we're exiting
        exit_code: Exit code (non-zero triggers respawn)
    """
    logger.error(f"FATAL: {reason}")
    logger.info("Writing patch for next respawn...")
    
    ResiliencePatch.save_patches()
    
    # Log heartbeat
    with open('logs/heartbeat.log', 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.now().isoformat()}] | EXIT | Reason: {reason}\n")
    
    logger.info("Exiting for respawn...")
    sys.exit(exit_code)


class Watchdog:
    """
    Watchdog timer to detect hung processes.
    Use to prevent zombie states.
    """
    
    def __init__(self, timeout_seconds: int = 600):
        """
        Initialize watchdog.
        
        Args:
            timeout_seconds: Max time without heartbeat before force exit
        """
        self.timeout = timeout_seconds
        self.last_heartbeat = time.time()
        
    def heartbeat(self):
        """Update heartbeat timestamp."""
        self.last_heartbeat = time.time()
        
    def check(self):
        """Check if process is hung."""
        elapsed = time.time() - self.last_heartbeat
        if elapsed > self.timeout:
            logger.error(f"Watchdog: No heartbeat for {elapsed:.0f}s. Force exit.")
            os._exit(1)  # Force exit, let wrapper respawn
        return elapsed < self.timeout


class ChaosInjector:
    """
    Inject chaos for testing resilience.
    Use only in test mode!
    """
    
    @staticmethod
    def kill_docker():
        """Kill Docker containers randomly."""
        import subprocess
        try:
            containers = subprocess.run(
                ['docker', 'ps', '-q'],
                capture_output=True, text=True, timeout=5
            )
            if containers.stdout.strip():
                container = containers.stdout.strip().split('\n')[0]
                subprocess.run(['docker', 'stop', container], timeout=10)
                logger.warning(f"Chaos: Killed container {container[:12]}")
        except Exception as e:
            logger.error(f"Chaos injection failed: {e}")
    
    @staticmethod
    def fill_disk(percent: float = 0.99):
        """Fill disk to simulate full disk."""
        try:
            import shutil
            total, used, free = shutil.disk_usage('/')
            target_size = int(total * percent) - used
            if target_size > 0:
                # Create a large file
                with open('logs/temp/junk.bin', 'wb') as f:
                    f.write(b'\x00' * min(target_size, 100 * 1024 * 1024))  # Max 100MB
                logger.warning(f"Chaos: Filled disk to {percent*100:.0f}%")
        except Exception as e:
            logger.error(f"Disk fill failed: {e}")
    
    @staticmethod
    def random_sleep(max_seconds: int = 30):
        """Random sleep to simulate slow operations."""
        import random
        delay = random.randint(1, max_seconds)
        logger.warning(f"Chaos: Sleeping for {delay}s")
        time.sleep(delay)


# Signal handler for graceful shutdown
def setup_signal_handlers():
    """Setup signal handlers for graceful shutdown."""
    def handler(signum, frame):
        logger.info(f"Received signal {signum}. Graceful exit...")
        graceful_exit("Signal received", 0)
    
    signal.signal(signal.SIGTERM, handler)
    signal.signal(signal.SIGINT, handler)


# Initialize on import
setup_signal_handlers()
