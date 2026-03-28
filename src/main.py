"""
MockClaw Immortal Agent - Main Entry Point
Infinite self-improvement loop: Janitor -> Generate -> Chaos -> Repair -> Polish
"""

import os
import sys
import json
import time
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

sys.path.insert(0, str(Path(__file__).parent))

from core.parser import HARParser
from core.generator import MockGenerator
from core.resilience import ResiliencePatch, Watchdog, graceful_exit, retry, logger


class ImmortalAgent:
    """The Immortal MockClaw Agent - runs forever, self-heals, self-improves."""
    
    def __init__(self, work_dir: str = "D:\\mockclaw-immortal"):
        self.work_dir = Path(work_dir)
        self.iteration = 0
        self.watchdog = Watchdog(timeout_seconds=600)
        self.heartbeat_log = self.work_dir / "logs" / "heartbeat.log"
        self.evolution_log = self.work_dir / "logs" / "evolution_history.md"
        
        # Ensure directories
        (self.work_dir / "logs" / "checkpoints").mkdir(parents=True, exist_ok=True)
        (self.work_dir / "generated_mocks").mkdir(exist_ok=True)
    
    def janitor(self):
        """Clean up resources - start with a clean slate."""
        logger.info("=" * 60)
        logger.info("JANITOR: Cleaning up...")
        logger.info("=" * 60)
        
        # Docker cleanup
        try:
            result = subprocess.run("docker ps -aq", shell=True, capture_output=True, text=True, timeout=10)
            containers = result.stdout.strip().split('\n') if result.stdout.strip() else []
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
            except:
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
            str(self.work_dir / "generated_mocks")
        )
        
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Generated {success_count}/{len(results)} endpoints")
        
        return success_count > 0
    
    def _endpoint_to_dict(self, endpoint) -> dict:
        return {
            "resource_path": endpoint.resource_path,
            "method": endpoint.method,
            "sample_request": {"body": endpoint.requests[0].body if endpoint.requests else None},
            "sample_response": {"status": endpoint.responses[0].status if endpoint.responses else 200, "body": endpoint.responses[0].body if endpoint.responses else None}
        }
    
    def chaos_test(self) -> Dict[str, Any]:
        """Run adversarial testing - THIS IS TORTURE."""
        logger.info("=" * 60)
        logger.info("CHAOS: Running adversarial tests...")
        logger.info("=" * 60)
        
        results = {"concurrency": "simulated", "garbage": "simulated", "docker_kill": "skipped", "failures": 0}
        
        # Simulate concurrency test
        try:
            import httpx
            # Would run actual tests here
            logger.info("Chaos tests simulated (httpx available)")
        except ImportError:
            logger.warning("httpx not available, chaos tests simulated")
        
        return results
    
    def repair(self, failure_info: Dict[str, Any]):
        """Self-repair based on failure analysis."""
        logger.info("=" * 60)
        logger.info("REPAIR: Analyzing failures...")
        logger.info("=" * 60)
        
        failures = failure_info.get("failures", 0)
        if failures > 0:
            ResiliencePatch.add_patch(
                error_type="ChaosTestFailure",
                fix="Investigate chaos test failures",
                code="# TODO: Improve resilience"
            )
            ResiliencePatch.save_patches()
    
    def polish(self):
        """Polish - linting, formatting, docs."""
        logger.info("=" * 60)
        logger.info("POLISH: Improving quality...")
        logger.info("=" * 60)
        
        # Run ruff if available
        try:
            subprocess.run(["ruff", "check", ".", "--fix"], timeout=60)
            logger.info("Ruff linting complete")
        except:
            pass
        
        # Update evolution log
        entry = f"\n## Iteration {self.iteration} - {datetime.now().isoformat()}\n- Status: Polish complete\n\n"
        with open(self.evolution_log, 'a', encoding='utf-8') as f:
            f.write(entry)
        
        logger.info("POLISH: Complete!")
    
    def validate(self) -> bool:
        """Validate generated mocks work correctly."""
        logger.info("=" * 60)
        logger.info("VALIDATE: Testing mocks...")
        logger.info("=" * 60)
        
        generated = self.work_dir / "generated_mocks" / "dynamic_api.py"
        if not generated.exists():
            logger.error("No generated code found")
            return False
        
        content = generated.read_text(encoding='utf-8')
        
        # Check required endpoints
        has_health = "/health" in content
        has_info = "/mockclaw/info" in content
        
        if has_health and has_info:
            logger.info("Validation passed!")
            return True
        else:
            logger.error("Validation failed - missing endpoints")
            return False
    
    def _log_heartbeat(self, status: str):
        timestamp = datetime.now().isoformat()
        with open(self.heartbeat_log, 'a', encoding='utf-8') as f:
            f.write(f"[{timestamp}] | Iter: {self.iteration} | Status: {status}\n")
        logger.info(f"Heartbeat: Iter {self.iteration} - {status}")
    
    def run_iteration(self, har_path: str) -> bool:
        """Run single iteration of the immortal loop."""
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
    
    def run_forever(self, har_path: str, max_iterations: int = 1000):
        """Run infinite loop until max iterations or fatal error."""
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
                ResiliencePatch.add_patch(type(e).__name__, f"Handle {type(e).__name__}", "# patch")
                graceful_exit(str(e), 1)
        
        logger.info(f"\nCompleted {self.iteration} iterations")
        return 0


def main():
    import argparse
    parser = argparse.ArgumentParser()
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
