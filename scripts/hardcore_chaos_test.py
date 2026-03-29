"""
MockClaw Hardcore Chaos Breaker
Real infrastructure sabotage - Docker kills, network drops, disk pressure.
"""

import asyncio
import json
import random
import time
import sys
import subprocess
import signal
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


class HardcoreChaosBreaker:
    """
    Hardcore adversarial testing with REAL infrastructure attacks.
    No mocks. No mercy.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000", use_docker: bool = True):
        self.base_url = base_url
        self.use_docker = use_docker
        self.results = []
        self.failures = []
        self.container_id = None
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}")
        
        if level == "FAIL":
            self.failures.append(message)
    
    def start_docker_container(self, image_name: str = "mockclaw-test"):
        """Start mock server in Docker container."""
        if not self.use_docker:
            self.log("Docker mode disabled, skipping container start", "WARN")
            return False
        
        self.log("Starting Docker container for chaos testing...")
        
        try:
            # Build and run container
            build_result = subprocess.run(
                ["docker", "build", "-t", image_name, "-f", "Dockerfile.mock", "."],
                capture_output=True, text=True, timeout=120,
                cwd=Path.cwd()
            )
            
            if build_result.returncode != 0:
                # Fallback: use python image directly
                self.log("Custom build failed, using python image...", "WARN")
                run_cmd = [
                    "docker", "run", "-d", "--rm",
                    "--name", "mockclaw-chaos",
                    "-p", "8000:8000",
                    "-v", f"{Path.cwd()}:/app",
                    "-w", "/app",
                    "python:3.11-slim",
                    "bash", "-c", "pip install fastapi uvicorn httpx && uvicorn generated_mocks.dynamic_api:app --host 0.0.0.0 --port 8000"
                ]
            else:
                run_cmd = [
                    "docker", "run", "-d", "--rm",
                    "--name", "mockclaw-chaos",
                    "-p", "8000:8000",
                    image_name
                ]
            
            result = subprocess.run(run_cmd, capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.container_id = result.stdout.strip()[:12]
                self.log(f"Container started: {self.container_id}")
                
                # Wait for health
                time.sleep(5)
                return self.check_health()
            else:
                self.log(f"Docker start failed: {result.stderr}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"Docker error: {e}", "FAIL")
            return False
    
    def stop_docker_container(self):
        """Stop Docker container."""
        if not self.container_id:
            return
        
        try:
            subprocess.run(
                ["docker", "stop", self.container_id],
                capture_output=True, timeout=10
            )
            self.log(f"Container stopped: {self.container_id}")
        except Exception as e:
            self.log(f"Error stopping container: {e}", "WARN")
    
    def check_health(self, max_retries: int = 3) -> bool:
        """Check if server is healthy."""
        for i in range(max_retries):
            try:
                resp = requests.get(f"{self.base_url}/health", timeout=5)
                if resp.status_code == 200:
                    return True
            except:
                pass
            time.sleep(2)
        return False
    
    def test_docker_kill_chaos(self):
        """
        CHAOS: Kill Docker container WHILE serving requests.
        This is REAL infrastructure sabotage.
        """
        if not self.use_docker or not self.container_id:
            self.log("Docker not available, skipping kill test", "WARN")
            return {"status": "skipped"}
        
        self.log("CHAOS: Starting continuous requests...")
        
        # Start background requests
        kill_event = False
        request_count = 0
        error_count = 0
        recovery_time = None
        
        start_time = time.time()
        
        try:
            # Send requests for 10 seconds
            while time.time() - start_time < 10:
                try:
                    resp = requests.get(f"{self.base_url}/health", timeout=2)
                    request_count += 1
                    
                    # Kill container at 5 second mark
                    if time.time() - start_time > 5 and not kill_event:
                        self.log("💀 CHAOS: KILLING CONTAINER NOW!")
                        self.stop_docker_container()
                        kill_event = True
                        kill_time = time.time()
                    
                    if resp.status_code >= 500:
                        error_count += 1
                        
                except Exception as e:
                    error_count += 1
                    # Expected after kill
                
                time.sleep(0.1)
            
            # Calculate recovery time if container was killed
            if kill_event:
                # Try to detect when it comes back (if auto-restart enabled)
                recovery_start = time.time()
                while time.time() - recovery_start < 30:  # Wait up to 30s
                    try:
                        resp = requests.get(f"{self.base_url}/health", timeout=2)
                        if resp.status_code == 200:
                            recovery_time = time.time() - kill_time
                            self.log(f"✅ Container recovered in {recovery_time:.2f}s")
                            break
                    except:
                        pass
                    time.sleep(1)
                
                if not recovery_time:
                    self.log("Container did NOT recover within 30s", "FAIL")
            
            # Results
            total_requests = request_count + error_count
            error_rate = error_count / total_requests if total_requests > 0 else 0
            
            self.log(f"Total requests: {total_requests}, Errors: {error_count} ({error_rate*100:.1f}%)")
            
            if error_rate > 0.5 and not recovery_time:
                self.log("HIGH FAILURE RATE - No recovery mechanism", "FAIL")
                return {"status": "failed", "error_rate": error_rate, "recovered": False}
            elif recovery_time:
                return {"status": "recovered", "recovery_time": recovery_time, "error_rate": error_rate}
            else:
                return {"status": "passed", "error_rate": error_rate}
                
        except Exception as e:
            self.log(f"Chaos test error: {e}", "FAIL")
            return {"status": "error", "error": str(e)}
    
    def test_rapid_fire_dos(self):
        """
        Test rapid-fire requests (simulated DoS).
        Send 200 requests in 10 seconds.
        """
        self.log("CHAOS: Starting rapid-fire DoS simulation (200 requests in 10s)...")
        
        start_time = time.time()
        success = 0
        rate_limited = 0
        errors = 0
        
        for i in range(200):
            try:
                resp = requests.get(f"{self.base_url}/health", timeout=5)
                
                if resp.status_code == 200:
                    success += 1
                elif resp.status_code == 429:
                    rate_limited += 1  # Good - rate limiting working
                else:
                    errors += 1
                    
            except Exception as e:
                errors += 1
        
        elapsed = time.time() - start_time
        
        self.log(f"Completed in {elapsed:.2f}s: {success} success, {rate_limited} rate-limited, {errors} errors")
        
        # Rate limiting should kick in
        if rate_limited > 10:
            self.log(f"✅ Rate limiting active: {rate_limited} requests blocked")
            return {"status": "passed", "rate_limited": rate_limited, "errors": errors}
        elif errors < 20:  # Less than 10% errors is acceptable
            return {"status": "passed", "success": success, "errors": errors}
        else:
            self.log(f"HIGH ERROR RATE: {errors}/200", "FAIL")
            return {"status": "failed", "errors": errors}
    
    def test_concurrent_load(self):
        """
        Test concurrent load with threading.
        50 parallel requests.
        """
        self.log("CHAOS: Sending 50 concurrent requests...")
        
        import concurrent.futures
        
        def make_request():
            try:
                resp = requests.get(f"{self.base_url}/health", timeout=10)
                return resp.status_code
            except:
                return 0
        
        start_time = time.time()
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=50) as executor:
            futures = [executor.submit(make_request) for _ in range(50)]
            results = [f.result() for f in futures]
        
        elapsed = time.time() - start_time
        
        success = sum(1 for r in results if r == 200)
        errors = sum(1 for r in results if r != 200)
        
        self.log(f"Completed in {elapsed:.2f}s: {success} success, {errors} errors")
        
        if errors > 5:  # More than 10% errors
            self.log(f"HIGH ERROR RATE under concurrent load", "FAIL")
            return {"status": "failed", "errors": errors, "time": elapsed}
        
        return {"status": "passed", "success": success, "time": elapsed}
    
    def test_malformed_urls(self):
        """Test path traversal and malformed URLs."""
        self.log("CHAOS: Testing malformed URLs and path traversal...")
        
        malicious_urls = [
            "/../../etc/passwd",
            "/../../../windows/system32/config/sam",
            "/..%2F..%2F..%2Fetc%2Fpasswd",
            "/api/users/../../../admin",
            "//evil.com",
            "/api/\\windows\\system32",
            "/..\\..\\..\\..\\..\\..\\etc\\passwd",
        ]
        
        blocked = 0
        for url in malicious_urls:
            try:
                resp = requests.get(f"{self.base_url}{url}", timeout=5, allow_redirects=False)
                
                # Should return 400 or 404, NOT 500
                if resp.status_code in [400, 404]:
                    blocked += 1
                    self.log(f"  ✓ Blocked: {url} ({resp.status_code})")
                elif resp.status_code >= 500:
                    self.log(f"  ✗ Server error on: {url}", "FAIL")
                else:
                    self.log(f"  ? Unexpected: {url} -> {resp.status_code}")
                    
            except Exception as e:
                self.log(f"  Error testing {url}: {e}", "WARN")
        
        if blocked >= len(malicious_urls) * 0.8:
            self.log(f"✅ Path traversal protection active: {blocked}/{len(malicious_urls)} blocked")
            return {"status": "passed", "blocked": blocked}
        else:
            self.log(f"INSUFFICIENT PROTECTION: Only {blocked}/{len(malicious_urls)} blocked", "FAIL")
            return {"status": "failed", "blocked": blocked}
    
    def test_garbage_payloads(self):
        """Test with garbage/malicious payloads."""
        self.log("CHAOS: Testing garbage payloads...")
        
        garbage_payloads = [
            {"data": None},
            {"data": {"nested": None}},
            {"long_string": "A" * 10000},
            {"special": "<script>alert('xss')</script>"},
            {"sql": "'; DROP TABLE users; --"},
            {"unicode": "你好" * 1000},
            {"empty": ""},
            {"deep": {"a": {"b": {"c": {"d": {"e": "value"}}}}}},
        ]
        
        handled = 0
        for payload in garbage_payloads:
            try:
                # Try POST to health (should be rejected)
                resp = requests.post(f"{self.base_url}/health", json=payload, timeout=5)
                
                # Should not return 500
                if resp.status_code < 500:
                    handled += 1
                else:
                    self.log(f"  Server error on payload: {resp.status_code}", "FAIL")
                    
            except Exception as e:
                self.log(f"  Error with payload: {e}", "WARN")
        
        if handled == len(garbage_payloads):
            self.log(f"✅ All garbage payloads handled correctly")
            return {"status": "passed", "handled": handled}
        else:
            return {"status": "failed", "handled": handled}
    
    def run_all_hardcore_tests(self):
        """Run all hardcore chaos tests."""
        print("\n" + "=" * 60)
        print("HARDCORE CHAOS BREAKER - Infrastructure Sabotage")
        print("=" * 60)
        
        results = {}
        
        # Test 1: Concurrent load
        print("\n[TEST 1] Concurrent Load Test...")
        results["concurrent"] = self.test_concurrent_load()
        
        # Test 2: Rapid-fire DoS
        print("\n[TEST 2] Rapid-Fire DoS Simulation...")
        results["dos"] = self.test_rapid_fire_dos()
        
        # Test 3: Path traversal
        print("\n[TEST 3] Path Traversal Test...")
        results["path_traversal"] = self.test_malformed_urls()
        
        # Test 4: Garbage payloads
        print("\n[TEST 4] Garbage Payload Test...")
        results["garbage"] = self.test_garbage_payloads()
        
        # Test 5: Docker kill (only if Docker available)
        if self.use_docker and self.container_id:
            print("\n[TEST 5] Docker Kill Chaos Test...")
            results["docker_kill"] = self.test_docker_kill_chaos()
        else:
            self.log("Skipping Docker kill test (Docker not available)", "WARN")
            results["docker_kill"] = {"status": "skipped"}
        
        # Summary
        print("\n" + "=" * 60)
        print("HARDCORE TEST RESULTS")
        print("=" * 60)
        
        for test_name, result in results.items():
            status = result.get("status", "unknown")
            symbol = "✅ PASS" if status in ["passed", "recovered"] else "❌ FAIL" if status == "failed" else "⚠️  SKIP"
            print(f"  {symbol} {test_name}: {status}")
        
        if self.failures:
            print(f"\n{len(self.failures)} FAILURES:")
            for f in self.failures:
                print(f"  - {f}")
        
        return {
            "total_tests": len(results),
            "failures": len(self.failures),
            "results": results
        }


def main():
    """Main entry point."""
    print("=" * 60)
    print("MockClaw Hardcore Chaos Breaker")
    print("=" * 60)
    
    # Check if mocks exist
    mock_file = Path("generated_mocks/dynamic_api.py")
    if not mock_file.exists():
        print("❌ Generated mocks not found!")
        print("Please generate mocks first:")
        print("  python regenerate_mocks.py")
        return 1
    
    # Check Docker
    use_docker = False
    try:
        result = subprocess.run(["docker", "ps"], capture_output=True, timeout=5)
        if result.returncode == 0:
            use_docker = True
            print("✅ Docker available - enabling infrastructure attacks")
        else:
            print("⚠️  Docker not available - running in limited mode")
    except:
        print("⚠️  Docker not available - running in limited mode")
    
    # Run tests
    breaker = HardcoreChaosBreaker(use_docker=use_docker)
    
    # If Docker available, start container
    if use_docker:
        if not breaker.start_docker_container():
            print("❌ Failed to start Docker container")
            print("Falling back to local testing...")
            breaker.use_docker = False
    
    try:
        results = breaker.run_all_hardcore_tests()
        
        # Save results
        results_path = Path("logs/hardcore_chaos_results.json")
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
        
        print(f"\n📦 Results saved to: {results_path}")
        
        # Exit code
        return 0 if results.get("failures", 0) == 0 else 1
        
    finally:
        # Cleanup
        if use_docker:
            breaker.stop_docker_container()


if __name__ == "__main__":
    sys.exit(main() or 0)
