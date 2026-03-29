"""
MockClaw Enhanced Chaos Breaker
Starts the mock server and runs adversarial tests against it.
"""

import asyncio
import json
import random
import string
import time
import sys
import subprocess
import signal
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


class EnhancedChaosBreaker:
    """
    Enhanced adversarial testing engine.
    Starts server, runs tests, cleans up.
    """
    
    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.results = []
        self.failures = []
        self.server_process = None
        
    def log(self, message: str, level: str = "INFO"):
        """Log message with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}")
        
        if level == "FAIL":
            self.failures.append(message)
    
    def start_mock_server(self):
        """Start the mock server from generated_mocks/dynamic_api.py."""
        self.log("Starting mock server...")
        
        mock_file = Path("generated_mocks/dynamic_api.py")
        if not mock_file.exists():
            self.log("Generated mock file not found. Running generator first...", "WARN")
            # Generate mocks first
            try:
                from core.parser import HARParser
                from core.generator import MockGenerator
                
                # Create test HAR
                test_har = {
                    "log": {
                        "version": "1.2",
                        "creator": {"name": "Chaos Test", "version": "0.1.0"},
                        "entries": [
                            {
                                "startedDateTime": "2026-03-28T10:00:00.000Z",
                                "time": 150,
                                "request": {
                                    "method": "POST",
                                    "url": "https://api.example.com/api/login",
                                    "httpVersion": "HTTP/1.1",
                                    "headers": [{"name": "Content-Type", "value": "application/json"}],
                                    "queryString": [],
                                    "postData": {
                                        "mimeType": "application/json",
                                        "text": '{"username":"testuser","password":"secret123"}'
                                    },
                                    "headersSize": -1,
                                    "bodySize": 45
                                },
                                "response": {
                                    "status": 200,
                                    "statusText": "OK",
                                    "httpVersion": "HTTP/1.1",
                                    "headers": [{"name": "Content-Type", "value": "application/json"}],
                                    "content": {
                                        "mimeType": "application/json",
                                        "text": '{"token":"mock_jwt_token","user":{"id":1,"username":"testuser"}}'
                                    },
                                    "redirectURL": "",
                                    "headersSize": -1,
                                    "bodySize": 150
                                },
                                "cache": {},
                                "timings": {"send": 0, "wait": 100, "receive": 10}
                            }
                        ]
                    }
                }
                
                test_file = Path("test_data/chaos_test.har")
                test_file.parent.mkdir(exist_ok=True)
                test_file.write_text(json.dumps(test_har), encoding='utf-8')
                
                # Generate
                parser = HARParser(str(test_file))
                endpoints_data = parser.export_as_dict()
                generator = MockGenerator()
                generator.generate_all(endpoints_data['endpoints'], "generated_mocks")
                
                self.log("Mock code generated")
                
            except Exception as e:
                self.log(f"Failed to generate mocks: {e}", "FAIL")
                return False
        
        # Start uvicorn server
        try:
            self.server_process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "generated_mocks.dynamic_api:app", "--host", "0.0.0.0", "--port", "8000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )
            
            # Wait for server to start
            self.log("Waiting for server to start...")
            time.sleep(3)
            
            # Health check
            try:
                import requests
                r = requests.get(f"{self.base_url}/health", timeout=5)
                if r.status_code == 200:
                    self.log("Server started successfully")
                    return True
                else:
                    self.log(f"Server returned {r.status_code}", "FAIL")
                    return False
            except Exception as e:
                self.log(f"Server health check failed: {e}", "FAIL")
                return False
                
        except Exception as e:
            self.log(f"Failed to start server: {e}", "FAIL")
            return False
    
    def stop_mock_server(self):
        """Stop the mock server."""
        if self.server_process:
            self.log("Stopping mock server...")
            try:
                if sys.platform == 'win32':
                    self.server_process.send_signal(signal.CTRL_BREAK_EVENT)
                else:
                    self.server_process.terminate()
                self.server_process.wait(timeout=5)
                self.log("Server stopped")
            except Exception as e:
                self.log(f"Error stopping server: {e}", "WARN")
                try:
                    self.server_process.kill()
                except:
                    pass
    
    async def test_concurrency(self, num_requests: int = 50):
        """Test concurrent request handling."""
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
                
                # Check response time
                if elapsed > 5.0:  # 50 requests in >5s is slow
                    self.log(f"SLOW RESPONSE: {elapsed:.2f}s for {num_requests} requests", "WARN")
                
                return {"status": "passed", "success": success, "failures": failures, "time": elapsed}
                
            except Exception as e:
                self.log(f"Concurrency test crashed: {e}", "FAIL")
                return {"status": "crashed", "error": str(e)}
    
    async def test_garbage_data(self):
        """Test with garbage input."""
        if not HTTPX_AVAILABLE:
            self.log("httpx not available, skipping garbage test", "WARN")
            return {"status": "skipped"}
        
        self.log("CHAOS: Sending garbage data...")
        
        # Test endpoints that accept POST - skip inf/nan as httpx can't serialize them
        garbage_tests = [
            # Null values
            {"data": None},
            {"data": {"nested": None, "value": None}},
            
            # Long strings
            {"long_string": "A" * 10000},  # 10k chars
            {"unicode": "你好" * 1000},
            
            # Special chars
            {"special": "<script>alert('xss')</script>"},
            {"sql": "'; DROP TABLE users; --"},
            
            # Edge cases
            {"empty_string": ""},
            {"spaces": "   "},
            {"newlines": "\n\n\n"},
            
            # Large structures
            {"large_array": list(range(1000))},
            {"deep_nesting": {"a": {"b": {"c": {"d": {"e": "value"}}}}}},
        ]
        
        # Use sync client for better reliability
        import requests
        server_errors = 0
        for i, garbage in enumerate(garbage_tests):
            try:
                # Try to send to any POST endpoint
                response = requests.post(f"{self.base_url}/health", json=garbage, timeout=10)
                
                if response.status_code >= 500:
                    self.log(f"Server error on garbage test {i}: {response.status_code}", "FAIL")
                    server_errors += 1
                elif response.status_code == 405:  # Method not allowed - expected
                    self.log(f"Garbage test {i}: Correctly rejected (405)")
                else:
                    self.log(f"Garbage test {i}: Handled gracefully (status {response.status_code})")
                        
            except requests.RequestException as e:
                self.log(f"Garbage test {i} request error: {e}", "WARN")
            except Exception as e:
                self.log(f"Garbage test {i} crashed: {e}", "WARN")
        
        if server_errors > 0:
            return {"status": "failed", "server_errors": server_errors}
        return {"status": "passed", "tests": len(garbage_tests)}
    
    async def test_malformed_urls(self):
        """Test with malformed URLs."""
        self.log("CHAOS: Testing malformed URLs...")
        
        malformed_urls = [
            "/../../etc/passwd",
            "/../../../windows/system32/config/sam",
            "/..%2F..%2F..%2Fetc%2Fpasswd",
            "/api/users/../../../admin",
            "//evil.com",
            "/api/\\windows\\system32",
        ]
        
        import requests
        successes = 0
        for url in malformed_urls:
            try:
                response = requests.get(f"{self.base_url}{url}", timeout=5)
                # Should not return 500
                if response.status_code >= 500:
                    self.log(f"Server error on malformed URL {url}: {response.status_code}", "FAIL")
                else:
                    self.log(f"Malformed URL handled: {url} -> {response.status_code}")
                    successes += 1
            except Exception as e:
                self.log(f"Malformed URL test error: {e}", "WARN")
        
        return {"status": "passed", "handled": len(malformed_urls)}
    
    async def test_rate_limiting(self):
        """Test rapid-fire requests to check for rate limiting or crashes."""
        self.log("CHAOS: Testing rate limiting (100 rapid requests)...")
        
        import requests
        start = time.time()
        errors = 0
        rate_limited = 0
        
        for i in range(100):
            try:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                if response.status_code >= 500:
                    errors += 1
                elif response.status_code == 429:
                    rate_limited += 1  # Expected - rate limiting working!
            except:
                errors += 1
        
        elapsed = time.time() - start
        
        # Rate limiting is GOOD - if we see 429s, that's a pass
        if rate_limited > 0:
            self.log(f"Rate limiting ACTIVE: {rate_limited}/100 requests rate-limited")
            return {"status": "passed", "time": elapsed, "rate_limited": rate_limited}
        
        if errors > 10:  # More than 10% errors
            self.log(f"High error rate under rapid requests: {errors}/100", "FAIL")
            return {"status": "failed", "errors": errors}
        
        self.log(f"Rapid fire: 100 requests in {elapsed:.2f}s, {errors} errors")
        return {"status": "passed", "time": elapsed, "errors": errors}
    
    def test_process_kill(self):
        """Kill server process and check recovery."""
        self.log("CHAOS: Killing server process...")
        
        if not self.server_process:
            self.log("No server process to kill", "WARN")
            return {"status": "skipped"}
        
        try:
            # Kill the process
            if sys.platform == 'win32':
                self.server_process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                self.server_process.terminate()
            
            self.server_process.wait(timeout=5)
            self.log("Server process killed")
            
            # Try to restart
            time.sleep(2)
            return self.start_mock_server()
            
        except Exception as e:
            self.log(f"Process kill test error: {e}", "WARN")
            return {"status": "error", "error": str(e)}
    
    async def run_all_chaos_tests(self):
        """Run all chaos tests."""
        print("\n" + "=" * 60)
        print("ENHANCED CHAOS BREAKER - Adversarial Testing")
        print("=" * 60)
        
        results = {}
        
        # Start server first
        if not self.start_mock_server():
            self.log("Failed to start server, aborting tests", "FAIL")
            return {"status": "aborted", "reason": "server_start_failed"}
        
        try:
            # Test 1: Concurrency
            print("\n[TEST 1] Concurrency Test...")
            results["concurrency"] = await self.test_concurrency(50)
            
            # Test 2: Garbage data
            print("\n[TEST 2] Garbage Data Test...")
            results["garbage"] = await self.test_garbage_data()
            
            # Test 3: Malformed URLs
            print("\n[TEST 3] Malformed URL Test...")
            results["malformed_urls"] = await self.test_malformed_urls()
            
            # Test 4: Rate limiting
            print("\n[TEST 4] Rate Limiting Test...")
            results["rate_limiting"] = await self.test_rate_limiting()
            
            # Test 5: Process kill (optional - may disrupt testing)
            # print("\n[TEST 5] Process Kill Test...")
            # results["process_kill"] = self.test_process_kill()
            
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
        
        finally:
            # Always cleanup
            self.stop_mock_server()


async def main():
    """Main entry point."""
    breaker = EnhancedChaosBreaker()
    results = await breaker.run_all_chaos_tests()
    
    # Save results
    results_path = Path("logs/chaos_results.json")
    results_path.parent.mkdir(parents=True, exist_ok=True)
    results_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
    
    print(f"\nResults saved to: {results_path}")
    
    # Return exit code based on results
    return 0 if results.get("failures", 0) == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
