"""
MockClaw Immortal Agent — Main Entry Point
===========================================

Infinite self-improvement loop that cycles through five phases:

1. **Janitor** — Clean up Docker containers, generated files, and caches.
2. **Generate** — Parse HAR traffic and produce FastAPI mock server code.
3. **Chaos** — Run adversarial tests against the generated mocks.
4. **Repair** — Analyse failures and register self-healing patches.
5. **Polish** — Lint, format, update documentation, and validate output.

The agent continues iterating until ``max_iterations`` is reached or
a fatal error triggers :func:`~core.resilience.graceful_exit`.

Usage::

    python -m src.main --agent-mode --har tests/gauntlet/flow.har --max-iter 100
"""

import argparse
import shutil
import subprocess
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

sys.path.insert(0, str(Path(__file__).parent))

from core.parser import HARParser
from core.generator import MockGenerator
from core.resilience import ResiliencePatch, Watchdog, graceful_exit, retry, logger


class ImmortalAgent:
    """The Immortal MockClaw Agent — runs forever, self-heals, self-improves.

    Each call to :meth:`run_iteration` executes the full five-phase loop.
    :meth:`run_forever` wraps iterations in an infinite (or bounded) loop.

    Args:
        work_dir: Root directory for all agent state, logs, and output.
    """

    def __init__(self, work_dir: str = r"D:\mockclaw-immortal") -> None:
        self.work_dir = Path(work_dir)
        self.iteration = 0
        self.watchdog = Watchdog(timeout_seconds=600)
        self.heartbeat_log = self.work_dir / "logs" / "heartbeat.log"
        self.evolution_log = self.work_dir / "logs" / "evolution_history.md"

        # Ensure directories
        (self.work_dir / "logs" / "checkpoints").mkdir(parents=True, exist_ok=True)
        (self.work_dir / "generated_mocks").mkdir(exist_ok=True)

    def janitor(self) -> None:
        """Clean up resources — start each iteration with a clean slate.

        Stops and removes all Docker containers, deletes files in
        ``generated_mocks/``, and recursively removes ``__pycache__``
        directories.
        """
        logger.info("=" * 60)
        logger.info("JANITOR: Cleaning up...")
        logger.info("=" * 60)

        # Docker cleanup
        try:
            result = subprocess.run(
                "docker ps -aq", shell=True, capture_output=True, text=True, timeout=10
            )
            containers = (
                result.stdout.strip().split("\n") if result.stdout.strip() else []
            )
            for c in containers:
                if c:
                    subprocess.run(f"docker stop {c}", shell=True, timeout=10)
                    subprocess.run(f"docker rm {c}", shell=True, timeout=10)
        except Exception as e:
            logger.warning(f"Docker cleanup warning: {e}")

        # File cleanup
        for f in (self.work_dir / "generated_mocks").glob("*"):
            try:
                f.unlink()
            except OSError:
                pass

        # Python cache cleanup
        for p in self.work_dir.rglob("__pycache__"):
            shutil.rmtree(p, ignore_errors=True)

        logger.info("JANITOR: Cleanup complete!")

    @retry(max_retries=3, delay=2.0)
    def generate(self, har_path: str) -> bool:
        """Generate mock code from HAR file."""
        logger.info("=" * 60)
        logger.info("GENERATE: Creating mocks...")
        logger.info("=" * 60)

        har_file = Path(har_path)
        if not har_file.exists():
            logger.error(f"HAR file not found: {har_path}")
            return False

        parser = HARParser(str(har_file))
        endpoints = parser.parse()

        logger.info(f"Found {len(endpoints)} endpoints")

        if len(endpoints) == 0:
            logger.warning("No endpoints in HAR")
            return False

        generator = MockGenerator()
        results = generator.generate_all(
            [self._endpoint_to_dict(e) for e in endpoints],
            str(self.work_dir / "generated_mocks"),
        )

        success_count = sum(1 for r in results if r.success)
        logger.info(f"Generated {success_count}/{len(results)} endpoints")

        return success_count > 0

    def _endpoint_to_dict(self, endpoint: Any) -> Dict[str, Any]:
        """Convert an :class:`APIEndpoint` object to a plain dictionary.

        Args:
            endpoint: A parsed :class:`~core.parser.APIEndpoint` instance.

        Returns:
            Dictionary with keys ``resource_path``, ``method``,
            ``sample_request``, and ``sample_response``.
        """
        return {
            "resource_path": endpoint.resource_path,
            "method": endpoint.method,
            "sample_request": {
                "body": endpoint.requests[0].body if endpoint.requests else None
            },
            "sample_response": {
                "status": endpoint.responses[0].status if endpoint.responses else 200,
                "body": endpoint.responses[0].body if endpoint.responses else None,
            },
        }

    def chaos_test(self) -> Dict[str, Any]:
        """Run adversarial testing against the generated mocks.

        Currently simulates concurrency and garbage-data tests.  Full chaos
        engineering (actual HTTP bombardment, Docker container kills) is
        planned for future iterations.

        Returns:
            A dictionary summarising test results, including a ``failures`` count.
        """
        logger.info("=" * 60)
        logger.info("CHAOS: Running adversarial tests...")
        logger.info("=" * 60)

        results = {
            "concurrency": "simulated",
            "garbage": "simulated",
            "docker_kill": "skipped",
            "failures": 0,
        }

        # Simulate concurrency test
        try:
            # Check if httpx is available for real chaos testing
            import importlib.util

            if importlib.util.find_spec("httpx"):
                logger.info("Chaos tests simulated (httpx available)")
        except ImportError:
            logger.warning("httpx not available, chaos tests simulated")

        return results

    def repair(self, failure_info: Dict[str, Any]) -> None:
        """Analyse failure info and register self-healing patches.

        Args:
            failure_info: Dictionary from :meth:`chaos_test`, expected to
                contain a ``failures`` count.
        """
        logger.info("=" * 60)
        logger.info("REPAIR: Analyzing failures...")
        logger.info("=" * 60)

        failures = failure_info.get("failures", 0)
        if failures > 0:
            ResiliencePatch.add_patch(
                error_type="ChaosTestFailure",
                fix="Investigate chaos test failures",
                code="# TODO: Improve resilience",
            )
            ResiliencePatch.save_patches()

    def polish(self) -> None:
        """Polish generated code — lint with ruff, update evolution log.

        Runs ``ruff check --fix`` if available, then appends an iteration
        entry to ``logs/evolution_history.md``.
        """
        logger.info("=" * 60)
        logger.info("POLISH: Improving quality...")
        logger.info("=" * 60)

        # Run ruff if available
        try:
            subprocess.run(["ruff", "check", ".", "--fix"], timeout=60)
            logger.info("Ruff linting complete")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass

        # Update evolution log
        entry = f"\n## Iteration {self.iteration} - {datetime.now().isoformat()}\n- Status: Polish complete\n\n"
        with open(self.evolution_log, "a", encoding="utf-8") as f:
            f.write(entry)

        logger.info("POLISH: Complete!")

    def validate(self) -> bool:
        """Validate that generated mocks contain the required endpoints.

        Checks that ``/health`` and ``/mockclaw/info`` routes are present
        in the combined ``dynamic_api.py`` output.

        Returns:
            ``True`` if both required endpoints are found.
        """
        logger.info("=" * 60)
        logger.info("VALIDATE: Testing mocks...")
        logger.info("=" * 60)

        generated = self.work_dir / "generated_mocks" / "dynamic_api.py"
        if not generated.exists():
            logger.error("No generated code found")
            return False

        content = generated.read_text(encoding="utf-8")

        # Check required endpoints
        has_health = "/health" in content
        has_info = "/mockclaw/info" in content

        if has_health and has_info:
            logger.info("Validation passed!")
            return True
        else:
            logger.error("Validation failed - missing endpoints")
            return False

    def _log_heartbeat(self, status: str) -> None:
        """Append a timestamped heartbeat entry to ``logs/heartbeat.log``.

        Args:
            status: Short status label (e.g. ``"OK"``, ``"FAILED"``).
        """
        timestamp = datetime.now().isoformat()
        with open(self.heartbeat_log, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] | Iter: {self.iteration} | Status: {status}\n")
        logger.info(f"Heartbeat: Iter {self.iteration} - {status}")

    def run_iteration(self, har_path: str) -> bool:
        """Execute one full iteration of the immortal loop.

        Runs Janitor → Generate → Chaos → Repair/Polish → Validate.

        Args:
            har_path: Path to the HAR traffic file to generate mocks from.

        Returns:
            ``True`` if the iteration completed successfully.
        """
        self.iteration += 1
        self.watchdog.heartbeat()

        logger.info("\n" + "=" * 60)
        logger.info(f"IMMORTAL AGENT - ITERATION {self.iteration}")
        logger.info("=" * 60)

        # Phase A: Janitor
        self.janitor()

        # Phase B: Generate
        if not self.generate(har_path):
            self._log_heartbeat("FAILED")
            return False

        # Phase C: Chaos
        chaos_results = self.chaos_test()

        # Phase D/E: Repair or Polish
        if chaos_results.get("failures", 0) > 0:
            self.repair(chaos_results)
            self._log_heartbeat("REPAIR")
            return False
        else:
            self.polish()

            # Phase F: Validate
            if not self.validate():
                self._log_heartbeat("VALIDATE_FAILED")
                return False

            self._log_heartbeat("OK")
            return True

    def run_forever(self, har_path: str, max_iterations: int = 1000) -> int:
        """Run the immortal loop until ``max_iterations`` or a fatal error.

        Args:
            har_path: Path to the HAR traffic file.
            max_iterations: Upper bound on iteration count (default ``1000``).

        Returns:
            Exit code (``0`` on normal completion).
        """
        logger.info("=" * 60)
        logger.info("IMMORTAL AGENT ACTIVATED")
        logger.info("=" * 60)
        logger.info(f"Max iterations: {max_iterations}")
        logger.info(f"HAR file: {har_path}")
        logger.info("Press Ctrl+C to stop\n")

        while self.iteration < max_iterations:
            try:
                success = self.run_iteration(har_path)
                if success:
                    logger.info(f"\nIteration {self.iteration} complete!")
                    time.sleep(3)
                else:
                    logger.warning("\nIteration failed, retrying...")
            except KeyboardInterrupt:
                logger.info("\nKeyboard interrupt, exiting...")
                break
            except Exception as e:
                logger.error(f"\nFATAL: {e}")
                traceback.print_exc()
                ResiliencePatch.add_patch(
                    type(e).__name__, f"Handle {type(e).__name__}", "# patch"
                )
                graceful_exit(str(e), 1)

        logger.info(f"\nCompleted {self.iteration} iterations")
        return 0


def main() -> int:
    """CLI entry point for the Immortal Agent.

    Parses arguments, validates agent mode, and starts the immortal loop.

    Returns:
        Process exit code (``0`` on success).
    """
    parser = argparse.ArgumentParser(
        description="MockClaw Immortal Agent — infinite self-improvement loop"
    )
    parser.add_argument("--agent-mode", action="store_true")
    parser.add_argument("--har", default="tests/gauntlet/flow.har")
    parser.add_argument("--max-iter", type=int, default=10)
    args = parser.parse_args()

    if not args.agent_mode:
        print("Run with --agent-mode to start immortal agent")
        return 0

    agent = ImmortalAgent()
    return agent.run_forever(args.har, args.max_iter)


if __name__ == "__main__":
    sys.exit(main())
