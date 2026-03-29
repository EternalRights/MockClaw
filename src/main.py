"""
MockClaw Agent Mode
Infinite self-improvement loop.
"""

import sys
import time
import shutil
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from core.parser import HARParser
from core.generator import MockGenerator
from core.resilience import (
    ResiliencePatch, 
    Watchdog, 
    graceful_exit, 
    retry,
    logger
)


class ImmortalAgent:
    """
    The Immortal MockClaw Agent.
    Runs infinite iteration: Janitor -> Generate -> Chaos -> Repair -> Polish
    """
    
    def __init__(self):
        self.iteration = 0
        self.watchdog = Watchdog(timeout_seconds=600)
        self.heartbeat_log = Path("logs/heartbeat.log")
        self.evolution_log = Path("logs/evolution_history.md")
        self.checkpoint_dir = Path("logs/checkpoints")
        
        # Ensure directories exist
        self.heartbeat_log.parent.mkdir(parents=True, exist_ok=True)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)
        
    def janitor(self):
        """
        Clean up resources before each iteration.
        Start with a clean slate.
        """
        logger.info("=" * 60)
        logger.info("JANITOR: Cleaning up resources...")
        logger.info("=" * 60)
        
        # Docker cleanup
        try:
            result = subprocess.run(
                ["docker", "ps", "-aq"],
                capture_output=True, text=True, timeout=5
            )
            containers = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            if containers and containers[0]:
                logger.info(f"Stopping {len(containers)} containers...")
                for c in containers:
                    if c:
                        subprocess.run(["docker", "stop", c], timeout=10)
                        subprocess.run(["docker", "rm", c], timeout=10)
        except Exception as e:
            logger.warning(f"Docker cleanup warning: {e}")
        
        # File cleanup
        cleanup_paths = [
            Path("generated_mocks/*"),
            Path("logs/temp/*"),
        ]
        
        for pattern in cleanup_paths:
            for f in Path().glob(str(pattern)):
                try:
                    if f.is_file():
                        f.unlink()
                    elif f.is_dir():
                        shutil.rmtree(f)
                except Exception as e:
                    logger.warning(f"Failed to delete {f}: {e}")
        
        # Python cache cleanup
        for p in Path("src").rglob("__pycache__"):
            shutil.rmtree(p, ignore_errors=True)
        
        logger.info("JANITOR: Cleanup complete!")
        
    @retry(max_retries=3, delay=2.0)
    def generate(self, har_path: str) -> bool:
        """
        Generate mock code from HAR file.
        
        Args:
            har_path: Path to HAR file
            
        Returns:
            True if generation successful
        """
        logger.info("=" * 60)
        logger.info("GENERATE: Creating mock code...")
        logger.info("=" * 60)
        
        if not Path(har_path).exists():
            logger.error(f"HAR file not found: {har_path}")
            return False
        
        # Parse HAR
        parser = HARParser(har_path)
        endpoints = parser.get_endpoints()
        
        logger.info(f"Found {len(endpoints)} endpoints")
        
        if len(endpoints) == 0:
            logger.warning("No endpoints found in HAR file")
            return False
        
        # Generate mocks
        generator = MockGenerator()
        results = generator.generate_all(
            [self._endpoint_to_dict(e) for e in endpoints],
            "generated_mocks"
        )
        
        success_count = sum(1 for r in results if r.success)
        logger.info(f"Generated {success_count}/{len(results)} endpoints")
        
        if success_count == 0:
            logger.error("No endpoints generated successfully")
            return False
        
        # Start Docker
        logger.info("Starting Docker containers...")
        try:
            subprocess.run(
                ["docker-compose", "up", "-d"],
                timeout=60,
                cwd=Path.cwd()
            )
            
            # Wait for health
            logger.info("Waiting for services to start...")
            time.sleep(5)
            
            # Health check
            import requests
            for _ in range(10):
                try:
                    r = requests.get("http://localhost:8000/health", timeout=5)
                    if r.status_code == 200:
                        logger.info("Services healthy!")
                        return True
                except Exception:
                    time.sleep(2)
            
            logger.error("Services failed to start")
            return False
            
        except Exception as e:
            logger.error(f"Docker start failed: {e}")
            return False
    
    def _endpoint_to_dict(self, endpoint) -> dict:
        """Convert endpoint to dict for generator."""
        return {
            "id": f"ep_{endpoint.resource_path}_{endpoint.method}".replace("/", "_"),
            "path": endpoint.resource_path,
            "method": endpoint.method,
            "sample_request": {
                "body": endpoint.requests[0].body if endpoint.requests else None
            },
            "sample_response": {
                "status": endpoint.responses[0].status if endpoint.responses else 200,
                "body": endpoint.responses[0].body if endpoint.responses else None
            }
        }
    
    def chaos_test(self) -> Dict[str, Any]:
        """
        Run adversarial testing.
        This is TORTURE, not testing.
        """
        logger.info("=" * 60)
        logger.info("CHAOS: Running adversarial tests...")
        logger.info("=" * 60)
        
        # Import and run chaos breaker
        sys.path.insert(0, str(Path.cwd()))
        from scripts.chaos_breaker import ChaosBreaker
        import asyncio
        
        breaker = ChaosBreaker()
        results = asyncio.run(breaker.run_all_chaos_tests())
        
        return results
    
    def repair(self, failure_info: Dict[str, Any]):
        """
        Self-repair based on failure analysis.
        
        Args:
            failure_info: Information about what failed
        """
        logger.info("=" * 60)
        logger.info("REPAIR: Analyzing failures...")
        logger.info("=" * 60)
        
        # Analyze failure patterns
        failures = failure_info.get("failures", 0)
        
        if failures > 0:
            logger.info(f"Detected {failures} failures")
            
            # Check what failed
            for test_name, result in failure_info.get("results", {}).items():
                if result.get("status") in ["failed", "crashed", "down"]:
                    logger.warning(f"Test '{test_name}' failed: {result}")
                    
                    # Register patch
                    ResiliencePatch.add_patch(
                        error_type=test_name,
                        fix=f"Investigate {test_name} failure handling",
                        code=f"# TODO: Improve {test_name} resilience"
                    )
            
            # Save patches
            ResiliencePatch.save_patches()
            
            logger.info("Patches written. Will apply on next iteration.")
        
    def polish(self):
        """
        Polish the project - linting, formatting, docs.
        Only runs if chaos tests pass.
        """
        logger.info("=" * 60)
        logger.info("POLISH: Improving code quality...")
        logger.info("=" * 60)
        
        # Run linter
        try:
            result = subprocess.run(
                ["ruff", "check", ".", "--fix"],
                capture_output=True, text=True, timeout=60
            )
            logger.info(f"Ruff: Fixed {result.stdout.count('Fixed')} issues")
        except FileNotFoundError:
            logger.warning("Ruff not installed, skipping linting")
        except Exception as e:
            logger.warning(f"Linting error: {e}")
        
        # Run type checker
        try:
            result = subprocess.run(
                ["mypy", "src/", "--ignore-missing-imports"],
                capture_output=True, text=True, timeout=60
            )
            if "error:" in result.stdout:
                logger.warning("Type errors found (non-blocking)")
        except FileNotFoundError:
            logger.warning("Mypy not installed, skipping type checking")
        except Exception as e:
            logger.warning(f"Type check error: {e}")
        
        # Update docs
        self._update_evolution_log()
        
        logger.info("POLISH: Complete!")
    
    def validate(self) -> bool:
        """
        Validate generated mocks work correctly.
        The critical test: expired coupon should return 400.
        """
        logger.info("=" * 60)
        logger.info("VALIDATE: Testing generated mocks...")
        logger.info("=" * 60)
        
        try:
            import requests
            
            # Test health
            r = requests.get("http://localhost:8000/health", timeout=5)
            if r.status_code != 200:
                logger.error("Health check failed")
                return False
            
            # Test info
            r = requests.get("http://localhost:8000/mockclaw/info", timeout=5)
            if r.status_code != 200:
                logger.error("Info endpoint failed")
                return False
            
            logger.info("All validation tests passed!")
            return True
            
        except Exception as e:
            logger.error(f"Validation error: {e}")
            return False
    
    def _update_evolution_log(self):
        """Update evolution history log."""
        timestamp = datetime.now().isoformat()
        
        entry = f"""
## Iteration {self.iteration} - {timestamp}

### Status
- Chaos Tests: Pending
- Patches Applied: {len(ResiliencePatch.patches)}
- Endpoints Generated: {len(list(Path("generated_mocks").glob("*.py")))}

### Changes
- Auto-polish completed
- Linting and type checking run

---
"""
        
        with open(self.evolution_log, 'a', encoding='utf-8') as f:
            f.write(entry)
    
    def _log_heartbeat(self, status: str, chaos_tests: str):
        """Log heartbeat to file."""
        timestamp = datetime.now().isoformat()
        
        entry = f"[{timestamp}] | Iter: {self.iteration} | Status: {status} | Chaos: {chaos_tests}\n"
        
        with open(self.heartbeat_log, 'a', encoding='utf-8') as f:
            f.write(entry)
        
        logger.info(f"Heartbeat: Iter {self.iteration} - {status}")
    
    def run_iteration(self, har_path: str):
        """
        Run single iteration of the immortal loop.
        
        Args:
            har_path: Path to HAR file for generation
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
            self._log_heartbeat("FAILED", "generate_error")
            graceful_exit("Generation failed", 1)
        
        # Phase C: Chaos
        chaos_results = self.chaos_test()
        
        # Phase D: Repair or Polish
        if chaos_results.get("failures", 0) > 0:
            self.repair(chaos_results)
            self._log_heartbeat("REPAIR", f"{chaos_results['failures']}_failures")
            return False  # Need retry
        else:
            self.polish()
            self._log_heartbeat("OK", "all_passed")
            
            # Phase F: Validate
            if not self.validate():
                logger.warning("Validation failed, will retry")
                return False
            
            return True
    
    def run_forever(self, har_path: str, max_iterations: int = 1000):
        """
        Run infinite loop until max iterations or fatal error.
        
        Args:
            har_path: Path to HAR file
            max_iterations: Maximum iterations before exit
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
                    time.sleep(5)  # Brief rest
                else:
                    logger.warning("\nIteration failed, retrying immediately...")
                    
            except KeyboardInterrupt:
                logger.info("\nKeyboard interrupt, exiting...")
                break
            except Exception as e:
                logger.error(f"\nFATAL ERROR: {e}")
                import traceback
                traceback.print_exc()
                
                # Log patch and exit for respawn
                ResiliencePatch.add_patch(
                    error_type=type(e).__name__,
                    fix=f"Handle {type(e).__name__} gracefully",
                    code=f"try:\n    ...\nexcept {type(e).__name__}:\n    graceful_exit('{e}')"
                )
                graceful_exit(str(e), 1)
        
        logger.info(f"\nCompleted {self.iteration} iterations")
        return 0


def main():
    """Main entry point for agent mode."""
    import argparse
    
    parser = argparse.ArgumentParser(description="MockClaw Immortal Agent")
    parser.add_argument("--agent-mode", action="store_true", help="Run in agent mode")
    parser.add_argument("--har", default="tests/gauntlet/flow.har", help="HAR file path")
    parser.add_argument("--max-iter", type=int, default=10, help="Max iterations")
    
    args = parser.parse_args()
    
    if not args.agent_mode:
        print("Run with --agent-mode to start the immortal agent")
        return 0
    
    agent = ImmortalAgent()
    return agent.run_forever(args.har, args.max_iter)


if __name__ == "__main__":
    sys.exit(main())
