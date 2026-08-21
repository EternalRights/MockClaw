"""
MockClaw Enhanced Chaos Breaker
Starts the mock server and runs adversarial tests against it.
"""

import asyncio
import argparse
import json
import math
import time
import sys
import subprocess
import signal
from pathlib import Path
from datetime import datetime
from typing import Any

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.parser import HARParser
from core.generator import MockGenerator


_GAUNTLET_HAR = Path(__file__).parent.parent / "tests" / "gauntlet" / "flow.har"

_MINIMAL_HAR = {
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
                    "postData": {"mimeType": "application/json", "text": '{"username":"testuser","password":"secret123"}'},
                    "headersSize": -1,
                    "bodySize": 45
                },
                "response": {
                    "status": 200,
                    "statusText": "OK",
                    "httpVersion": "HTTP/1.1",
                    "headers": [{"name": "Content-Type", "value": "application/json"}],
                    "content": {"mimeType": "application/json", "text": '{"token":"mock_jwt_token","user":{"id":1,"username":"testuser"}}'},
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


def _percentile(sorted_values: list[float], pct: float) -> float:
    """Return the ``pct``-th percentile of a pre-sorted list of values.

    Uses the nearest-rank method. Returns ``0.0`` for an empty list.
    """
    if not sorted_values:
        return 0.0
    idx = max(0, int(math.ceil(pct / 100.0 * len(sorted_values))) - 1)
    return sorted_values[idx]


def _format_ms(value: float) -> float:
    """Round a millisecond value to two decimal places for reporting."""
    return round(value, 2)


class EnhancedChaosBreaker:
    """Enhanced adversarial testing engine."""

    def __init__(self, base_url: str = "http://localhost:8000", mock_dir: str = "generated_mocks") -> None:
        self.base_url = base_url
        self.mock_dir = Path(mock_dir)
        self.results: list[dict[str, Any]] = []
        self.failures: list[str] = []
        self.server_process: subprocess.Popen | None = None

    def log(self, message: str, level: str = "INFO") -> None:
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        print(f"[{timestamp}] [{level}] {message}")
        if level == "FAIL":
            self.failures.append(message)

    def _wait_for_server(self, timeout: float = 15.0) -> bool:
        """Poll /health until the server is ready or timeout."""
        import requests as req_lib
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                r = req_lib.get(f"{self.base_url}/health", timeout=2)
                if r.status_code == 200:
                    return True
            except req_lib.RequestException:
                pass
            time.sleep(0.5)
        return False

    def start_mock_server(self):
        self.log("Starting mock server...")

        mock_file = self.mock_dir / "dynamic_api.py"
        if not mock_file.exists():
            self.log("Generated mock file not found. Running generator first...", "WARN")
            try:
                har_source = str(_GAUNTLET_HAR) if _GAUNTLET_HAR.exists() else None
                if har_source is None:
                    test_file = Path("test_data/chaos_test.har")
                    test_file.parent.mkdir(exist_ok=True)
                    test_file.write_text(json.dumps(_MINIMAL_HAR), encoding='utf-8')
                    har_source = str(test_file)

                parser = HARParser(har_source)
                endpoints_data = parser.export_as_dict()
                generator = MockGenerator(use_smart_fallback=True)
                generator.generate_all(endpoints_data['endpoints'], str(self.mock_dir))
                self.log("Mock code generated")
            except Exception as e:
                self.log(f"Failed to generate mocks: {e}", "FAIL")
                return False

        try:
            module_path = f"{self.mock_dir.name}.dynamic_api:app"
            self.server_process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", module_path, "--host", "0.0.0.0", "--port", "8000"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
            )

            parent_dir = str(self.mock_dir.resolve().parent)
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)

            self.log("Waiting for server to start...")
            if self._wait_for_server():
                self.log("Server started successfully")
                return True
            else:
                self.log("Server health check timed out", "FAIL")
                return False

        except Exception as e:
            self.log(f"Failed to start server: {e}", "FAIL")
            return False

    def stop_mock_server(self):
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
                except Exception:
                    pass

    async def test_concurrency(self, num_requests: int = 50):
        try:
            import httpx
        except ImportError:
            self.log("httpx not available, skipping concurrency test", "WARN")
            return {"status": "skipped"}

        self.log(f"CHAOS: Sending {num_requests} parallel requests...")

        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
            tasks = [client.get("/health") for _ in range(num_requests)]
            start = time.time()
            try:
                results = await asyncio.gather(*tasks, return_exceptions=True)
                elapsed = time.time() - start

                success = sum(1 for r in results if isinstance(r, httpx.Response) and r.status_code == 200)
                failures = sum(1 for r in results if isinstance(r, Exception))

                self.log(f"Completed {num_requests} requests in {elapsed:.2f}s")
                self.log(f"Success: {success}, Failures: {failures}")

                if failures > num_requests * 0.1:
                    self.log(f"HIGH FAILURE RATE: {failures}/{num_requests}", "FAIL")
                    return {"status": "failed", "failures": failures}

                if elapsed > 5.0:
                    self.log(f"SLOW RESPONSE: {elapsed:.2f}s for {num_requests} requests", "WARN")

                return {"status": "passed", "success": success, "failures": failures, "time": elapsed}

            except Exception as e:
                self.log(f"Concurrency test crashed: {e}", "FAIL")
                return {"status": "crashed", "error": str(e)}

    async def test_garbage_data(self):
        self.log("CHAOS: Sending garbage data...")

        garbage_tests = [
            {"data": None},
            {"data": {"nested": None, "value": None}},
            {"long_string": "A" * 10000},
            {"unicode": "\u4f60\u597d" * 1000},
            {"special": "<script>alert('xss')</script>"},
            {"sql": "'; DROP TABLE users; --"},
            {"empty_string": ""},
            {"spaces": "   "},
            {"newlines": "\n\n\n"},
            {"large_array": list(range(1000))},
            {"deep_nesting": {"a": {"b": {"c": {"d": {"e": "value"}}}}}},
        ]

        import requests
        server_errors = 0
        for i, garbage in enumerate(garbage_tests):
            try:
                response = requests.post(f"{self.base_url}/api/login", json=garbage, timeout=10)
                if response.status_code >= 500:
                    self.log(f"Server error on garbage test {i}: {response.status_code}", "FAIL")
                    server_errors += 1
                else:
                    self.log(f"Garbage test {i}: Handled gracefully (status {response.status_code})")
            except requests.RequestException as e:
                self.log(f"Garbage test {i} request error: {e}", "WARN")

        if server_errors > 0:
            return {"status": "failed", "server_errors": server_errors}
        return {"status": "passed", "tests": len(garbage_tests)}

    async def test_malformed_urls(self):
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
        for url in malformed_urls:
            try:
                response = requests.get(f"{self.base_url}{url}", timeout=5)
                if response.status_code >= 500:
                    self.log(f"Server error on malformed URL {url}: {response.status_code}", "FAIL")
                else:
                    self.log(f"Malformed URL handled: {url} -> {response.status_code}")
            except requests.RequestException as e:
                self.log(f"Malformed URL test error: {e}", "WARN")

        return {"status": "passed", "handled": len(malformed_urls)}

    async def test_rate_limiting(self):
        self.log("CHAOS: Testing rate limiting (100 rapid requests)...")

        import requests
        start = time.time()
        errors = 0
        rate_limited = 0

        for _ in range(100):
            try:
                response = requests.get(f"{self.base_url}/health", timeout=5)
                if response.status_code >= 500:
                    errors += 1
                elif response.status_code == 429:
                    rate_limited += 1
            except requests.RequestException:
                errors += 1

        elapsed = time.time() - start

        if rate_limited > 0:
            self.log(f"Rate limiting ACTIVE: {rate_limited}/100 requests rate-limited")
            return {"status": "passed", "time": elapsed, "rate_limited": rate_limited}

        if errors > 10:
            self.log(f"High error rate under rapid requests: {errors}/100", "FAIL")
            return {"status": "failed", "errors": errors}

        self.log(f"Rapid fire: 100 requests in {elapsed:.2f}s, {errors} errors")
        return {"status": "passed", "time": elapsed, "errors": errors}

    async def test_latency(self, num_requests: int = 30) -> dict[str, Any]:
        """Benchmark endpoint latency and report percentile statistics.

        Sends ``num_requests`` sequential GET requests to ``/health`` and
        reports min/max/avg as well as p50/p95/p99 percentiles. Useful for
        validating that ``--simulate-latency`` generated mocks behave
        realistically, or for detecting unexpected slow endpoints.
        """
        try:
            import httpx
        except ImportError:
            self.log("httpx not available, skipping latency test", "WARN")
            return {"status": "skipped"}

        self.log(f"CHAOS: Benchmarking latency ({num_requests} requests)...")

        latencies: list[float] = []
        async with httpx.AsyncClient(base_url=self.base_url, timeout=30) as client:
            for _ in range(num_requests):
                start = time.perf_counter()
                try:
                    await client.get("/health")
                    latencies.append((time.perf_counter() - start) * 1000)
                except Exception as exc:
                    self.log(f"Latency test request failed: {exc}", "WARN")

        if not latencies:
            return {"status": "failed", "reason": "no_successful_requests"}

        sorted_latencies = sorted(latencies)
        stats = {
            "count": len(latencies),
            "min_ms": _format_ms(sorted_latencies[0]),
            "max_ms": _format_ms(sorted_latencies[-1]),
            "avg_ms": _format_ms(sum(latencies) / len(latencies)),
            "p50_ms": _format_ms(_percentile(sorted_latencies, 50)),
            "p95_ms": _format_ms(_percentile(sorted_latencies, 95)),
            "p99_ms": _format_ms(_percentile(sorted_latencies, 99)),
        }
        self.log(
            "Latency stats: "
            f"avg={stats['avg_ms']}ms p50={stats['p50_ms']}ms "
            f"p95={stats['p95_ms']}ms p99={stats['p99_ms']}ms"
        )
        return {"status": "passed", **stats}

    async def run_all_chaos_tests(
        self,
        only: list[str] | None = None,
        json_output: bool = False,
    ) -> dict[str, Any]:
        test_suite = [
            ("concurrency", "Concurrency Test", self.test_concurrency),
            ("garbage", "Garbage Data Test", self.test_garbage_data),
            ("malformed_urls", "Malformed URL Test", self.test_malformed_urls),
            ("rate_limiting", "Rate Limiting Test", self.test_rate_limiting),
            ("latency", "Latency Benchmark", self.test_latency),
        ]

        if only:
            test_suite = [
                (name, label, fn)
                for name, label, fn in test_suite
                if name in only
            ]

        print("\n" + "=" * 60)
        print("ENHANCED CHAOS BREAKER - Adversarial Testing")
        print("=" * 60)

        results: dict[str, Any] = {}

        if not self.start_mock_server():
            self.log("Failed to start server, aborting tests", "FAIL")
            return {"status": "aborted", "reason": "server_start_failed"}

        try:
            for idx, (name, label, fn) in enumerate(test_suite, start=1):
                print(f"\n[TEST {idx}] {label}...")
                results[name] = await fn()

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

            summary = {
                "total_tests": len(results),
                "failures": len(self.failures),
                "results": results,
            }

            if json_output:
                print("\n" + json.dumps(summary, indent=2))

            return summary

        finally:
            self.stop_mock_server()


def _parse_args(argv: list[str]) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run adversarial chaos tests against a MockClaw mock server.",
    )
    parser.add_argument(
        "mock_dir",
        nargs="?",
        default="generated_mocks",
        help="Directory containing generated mocks (default: generated_mocks)",
    )
    parser.add_argument(
        "--base-url",
        default="http://localhost:8000",
        help="Base URL of the running mock server (default: http://localhost:8000)",
    )
    parser.add_argument(
        "--only",
        help="Comma-separated list of test names to run (e.g. latency,rate_limiting)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Print the final summary as JSON to stdout",
    )
    return parser.parse_args(argv)


async def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv if argv is not None else sys.argv[1:])

    only = [name.strip() for name in args.only.split(",")] if args.only else None

    breaker = EnhancedChaosBreaker(base_url=args.base_url, mock_dir=args.mock_dir)

    results: dict[str, Any] = {"status": "aborted", "total_tests": 0, "failures": 0, "results": {}}

    try:
        results = await breaker.run_all_chaos_tests(only=only, json_output=args.json_output)
    except Exception as e:
        print(f"Chaos test error: {e}")
        results = {
            "status": "error",
            "total_tests": 0,
            "failures": 1,
            "error": str(e),
            "results": {}
        }
    finally:
        results_path = Path("logs/chaos_results.json")
        results_path.parent.mkdir(parents=True, exist_ok=True)
        results_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
        print(f"\nResults saved to: {results_path}")

    return 0 if results.get("failures", 0) == 0 else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
