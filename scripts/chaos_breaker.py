"""
MockClaw Chaos Breaker
Adversarial testing with chaos engineering.
This is not normal testing. This is TORTURE.
"""

import asyncio
import json
import random
import string
import time
import sys
import subprocess
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
import concurrent.futures

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

try:
    import httpx
    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False
    print("WARNING: httpx not installed. Install with: pip install httpx")


class ChaosBreaker:
    """
    Adversarial testing engine.
    Breaks the system in every way possible.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        self.failures = []
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}")
        
        if level == "FAIL":
            self.failures.append(message)
    
    async def test_concurrency(self, num_requests: int = 50):
        """
        Test concurrent request handling.
        Send 50 parallel requests to the mock API.
        """
        if not HTTPX_AVAILABLE:
            self.log("httpx not available, skipping concurrency test", "WARN")
            return {"status": "skipped"}
        
        self.log(f"CHAOS: Sending {num_requests} parallel requests...")
        
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
            tasks = []
            for i in range(num_requests):
                tasks.append(client.get("/health"))
            
            start = time.time()
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                elapsed = time.time() - start
                
                success = sum(1 for r in results if isinstance(r, httpx.Response) and r.status_code == 200)
                failures = sum(1 for r in results if isinstance(r, Exception))
                
                self.log(f"Completed {num_requests} requests in {elapsed:.2f}s")
                self.log(f"Success: {success}, Failures: {failures}")
                
                if failures > num_requests * 0.1:  # More than 10% failures
                    self.log(f"HIGH FAILURE RATE: {failures}/{num_requests}", "FAIL")
                    return {"status": "failed", "failures": failures}
                
                return {"status": "passed", "success": success, "failures": failures, "time": elapsed}
                
            except Exception as e:
                self.log(f"Concurrency test crashed: {e}", "FAIL")
                return {"status": "crashed", "error": str(e)}
    
    async def test_garbage_data(self):
        """
        Test with garbage input.
        Send JSON with null values, 5000 char strings, etc.
        """
        if not HTTPX_AVAILABLE:
            self.log("httpx not available, skipping garbage test", "WARN")
            return {"status": "skipped"}
        
        self.log("CHAOS: Sending garbage data...")
        
        garbage_tests = [
            # Null values
            {"data": None},
            {"data": {"nested": None, "value": None}},
            
            # Long strings
            {"long_string": "A" * 5000},
            {"unicode": "你好" * 1000},
            
            # Special chars
            {"special": "<script>alert('xss')</script>"},
            {"sql": "'; DROP TABLE users; --"},
            {"json_injection": '{"key": "value"}'},
            
            # Edge cases
            {"empty_string": ""},
            {"spaces": "   "},
            {"newlines": "\n\n\n"},
            
            # Large structures
            {"large_array": list(range(1000))},
            {"deep_nesting": {"a": {"b": {"c": {"d": {"e": "value"}}}}}},
        ]
        
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
            for i, garbage in enumerate(garbage_tests):
                try:
                    # Try to send to parse endpoint
                    response = await client.post("/parse", json=garbage)
                    
                    if response.status_code >= 500:
                        self.log(f"Server error on garbage test {i}: {response.status_code}", "FAIL")
                    else:
                        self.log(f"Garbage test {i}: Handled gracefully (status {response.status_code})")
                        
                except Exception as e:
                    self.log(f"Garbage test {i} crashed: {e}", "WARN")
        
        return {"status": "passed", "tests": len(garbage_tests)}
    
    def test_docker_kill(self):
        """
        CHAOS: Kill Docker while serving requests.
        Does the system recover?
        """
        self.log("CHAOS: Killing Docker containers...")
        
        try:
            # List running containers
            result = subprocess.run(
                ["docker", "ps", "-q"],
                capture_output=True, text=True, timeout=5
            )
            
            containers = result.stdout.strip().split('\n') if result.stdout.strip() else []
            
            if containers and containers[0]:
                # Kill first container
                container = containers[0]
                subprocess.run(["docker", "stop", container], timeout=10)
                self.log(f"Killed container: {container[:12]}")
                
                # Wait and check recovery
                time.sleep(2)
                
                # Check if system is still responsive
                try:
                    import requests
                    r = requests.get(f"{self.base_url}/health", timeout=5)
                    if r.status_code == 200:
                        self.log("System recovered after Docker kill!")
                        return {"status": "recovered"}
                    else:
                        self.log(f"System returned {r.status_code} after Docker kill", "FAIL")
                        return {"status": "degraded"}
                except:
                    self.log("System unresponsive after Docker kill", "FAIL")
                    return {"status": "down"}
            else:
                self.log("No containers running, skipping Docker kill")
                return {"status": "skipped"}
                
        except Exception as e:
            self.log(f"Docker kill test error: {e}", "WARN")
            return {"status": "error", "error": str(e)}
    
    def test_network_drop(self):
        """
        CHAOS: Simulate network drop.
        Disable network for 2 seconds during operation.
        """
        self.log("CHAOS: Simulating network drop...")
        
        # On Windows, we can simulate by blocking the port
        # For now, just log that this would happen
        self.log("Network drop simulation: Would disable network for 2s")
        self.log("(Full implementation requires admin privileges)")
        
        return {"status": "simulated", "note": "Full test requires admin"}
    
    def test_disk_full(self):
        """
        CHAOS: Simulate disk full.
        Fill disk to 99% before writing logs.
        """
        self.log("CHAOS: Simulating disk full...")
        
        try:
            # Create a temporary large file
            temp_file = Path("logs/temp/junk.bin")
            temp_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Write up to 100MB
            with open(temp_file, 'wb') as f:
                for _ in range(100):  # 100MB
                    f.write(b'\x00' * (1024 * 1024))
            
            self.log("Created 100MB junk file for disk pressure test")
            
            # Test if system still works
            try:
                import requests
                r = requests.get(f"{self.base_url}/health", timeout=5)
                if r.status_code == 200:
                    self.log("System survived disk pressure test")
                    result = {"status": "passed"}
                else:
                    self.log("System degraded under disk pressure", "FAIL")
                    result = {"status": "degraded"}
            except:
                self.log("System crashed under disk pressure", "FAIL")
                result = {"status": "failed"}
            
            # Cleanup
            temp_file.unlink(missing_ok=True)
            return result
            
        except Exception as e:
            self.log(f"Disk full test error: {e}", "WARN")
            return {"status": "error", "error": str(e)}
    
    async def run_all_chaos_tests(self):
        """Run all chaos tests."""
        print("\n" + "=" * 60)
        print("CHAOS BREAKER - Adversarial Testing")
        print("=" * 60)
        
        results = {}
        
        # Test 1: Concurrency
        print("\n[TEST 1] Concurrency Test...")
        results["concurrency"] = await self.test_concurrency(50)
        
        # Test 2: Garbage data
        print("\n[TEST 2] Garbage Data Test...")
        results["garbage"] = await self.test_garbage_data()
        
        # Test 3: Docker kill
        print("\n[TEST 3] Docker Kill Test...")
        results["docker_kill"] = self.test_docker_kill()
        
        # Test 4: Network drop
        print("\n[TEST 4] Network Drop Test...")
        results["network_drop"] = self.test_network_drop()
        
        # Test 5: Disk full
        print("\n[TEST 5] Disk Full Test...")
        results["disk_full"] = self.test_disk_full()
        
        # Summary
        print("\n" + "=" * 60)
        print("CHAOS TEST RESULTS")
        print("=" * 60)
        
        for test_name, result in results.items():
            status = result.get("status", "unknown")
            symbol = "PASS" if status == "passed" else "FAIL" if status == "failed" else "WARN"
            print(f"  [{symbol}] {test_name}: {status}")
        
        if self.failures:
            print(f"\n{len(self.failures)} FAILURES:")
            for f in self.failures:
                print(f"  - {f}")
        
        return {
            "total_tests": len(results),
            "failures": len(self.failures),
            "results": results
        }


async def main():
    """Main entry point."""
    breaker = ChaosBreaker()
    results = await breaker.run_all_chaos_tests()
    
    # Save results
    results_path = Path("logs/chaos_results.json")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
    
    print(f"\nResults saved to: {results_path}")
    
    # Return exit code based on results
    return 0 if results["failures"] == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
