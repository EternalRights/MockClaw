"""
Chaos test utility tests.

Covers the pure helper functions in scripts/enhanced_chaos_test.py
(percentile calculation and millisecond formatting) which are the
deterministic, testable parts of the chaos engine.
"""

import asyncio
import os
import sys
from pathlib import Path

import pytest
import requests

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

import enhanced_chaos_test as chaos  # noqa: E402
from enhanced_chaos_test import _percentile, _format_ms, _exit_code  # noqa: E402


class TestPercentile:
    def test_empty_list_returns_zero(self):
        assert _percentile([], 50) == 0.0

    def test_single_value(self):
        assert _percentile([42.0], 99) == 42.0

    def test_p50_of_even_list(self):
        values = [10.0, 20.0, 30.0, 40.0]
        assert _percentile(values, 50) == 20.0

    def test_p100_returns_max(self):
        values = [5.0, 10.0, 15.0, 20.0, 25.0]
        assert _percentile(values, 100) == 25.0

    def test_p0_returns_min(self):
        values = [5.0, 10.0, 15.0, 20.0, 25.0]
        assert _percentile(values, 0) == 5.0

    def test_p95_of_range(self):
        values = [float(i) for i in range(1, 101)]  # 1..100
        assert _percentile(values, 95) == 95.0


class TestFormatMs:
    def test_rounds_to_two_decimals(self):
        assert _format_ms(1.23456) == 1.23

    def test_preserves_integers(self):
        assert _format_ms(5.0) == 5.0

    def test_zero(self):
        assert _format_ms(0.0) == 0.0


class TestExitCode:
    """An aborted run must not be reported as a clean one.

    The abort result carried no ``failures`` key, so the count-based decision
    read it as zero: `mockclaw test` printed "All chaos tests passed!" and
    exited 0 after the suite had failed to start its mock server.
    """

    def test_completed_run_without_failures_succeeds(self):
        assert _exit_code({"total_tests": 5, "failures": 0, "results": {}}) == 0

    def test_completed_run_with_failures_fails(self):
        assert _exit_code({"total_tests": 5, "failures": 2, "results": {}}) == 1

    def test_aborted_run_fails_even_with_no_failed_test(self):
        # No test failed because none ran; the run itself did.
        assert _exit_code({
            "status": "aborted",
            "reason": "server_start_failed",
            "total_tests": 0,
            "failures": 0,
            "results": {},
        }) == 1

    def test_bare_abort_result_fails(self):
        # The shape this used to return: no count to read at all.
        assert _exit_code({"status": "aborted", "reason": "server_start_failed"}) == 1

    def test_error_run_fails(self):
        assert _exit_code({"status": "error", "failures": 1}) == 1

    def test_the_default_result_before_a_run_fails(self):
        assert _exit_code({
            "status": "aborted", "total_tests": 0, "failures": 0, "results": {},
        }) == 1


class TestSummaryFailureCount:
    """A test that fails must make the whole run fail, however it reported.

    ``failures`` counted FAIL log lines only. A test that returns a "failed"
    status without logging one -- the latency benchmark answers
    "no_successful_requests" when every request raised -- left the count at
    zero, so the summary printed a [FAIL] row and the run still exited 0.
    """

    def _breaker(self, monkeypatch):
        breaker = chaos.EnhancedChaosBreaker(base_url="http://127.0.0.1:1")
        monkeypatch.setattr(breaker, "start_mock_server", lambda: True)
        monkeypatch.setattr(breaker, "stop_mock_server", lambda: None)
        return breaker

    def test_a_failed_status_without_a_log_line_fails_the_run(self, monkeypatch):
        breaker = self._breaker(monkeypatch)

        async def failing_latency(num_requests: int = 30):
            return {"status": "failed", "reason": "no_successful_requests"}

        monkeypatch.setattr(breaker, "test_latency", failing_latency)

        summary = asyncio.run(breaker.run_all_chaos_tests(only=["latency"]))

        assert summary["failed_tests"] == ["latency"]
        assert summary["failures"] == 1
        assert _exit_code(summary) == 1

    def test_a_logged_failure_is_still_counted_once(self, monkeypatch):
        # A test that both logs a FAIL line and reports itself failed is one
        # failing test, not two.
        breaker = self._breaker(monkeypatch)

        async def failing_garbage():
            breaker.log("boom", "FAIL")
            return {"status": "failed", "server_errors": 1}

        monkeypatch.setattr(breaker, "test_garbage_data", failing_garbage)

        summary = asyncio.run(breaker.run_all_chaos_tests(only=["garbage"]))

        assert summary["failures"] == 1
        assert _exit_code(summary) == 1


class _Resp500:
    status_code = 500


class _Resp400:
    status_code = 400


class TestMalformedUrlReporting:
    """A malformed URL answered with 5xx is a failure, not a pass.

    The test logged FAIL for each 5xx and then returned "passed", so the
    results table printed PASS next to the failures it had just recorded.
    """

    def test_a_server_error_is_reported_as_failed(self, monkeypatch):
        monkeypatch.setattr(requests, "get", lambda url, timeout=None: _Resp500())
        breaker = chaos.EnhancedChaosBreaker(base_url="http://127.0.0.1:1")

        result = asyncio.run(breaker.test_malformed_urls())

        assert result["status"] == "failed"
        assert result["server_errors"] == 6
        assert len(breaker.failures) == 6

    def test_a_handled_url_is_reported_as_passed(self, monkeypatch):
        monkeypatch.setattr(requests, "get", lambda url, timeout=None: _Resp400())
        breaker = chaos.EnhancedChaosBreaker(base_url="http://127.0.0.1:1")

        result = asyncio.run(breaker.test_malformed_urls())

        assert result["status"] == "passed"
        assert breaker.failures == []


class TestSpawnedMockServer:
    """How the mock server is spawned decides whether the suite can run.

    Two faults compounded: the child was never told where the mock package
    lives (so a mock dir outside the current directory died with "No module
    named 'mocks'"), and its output went to pipes nobody drained (so
    uvicorn's per-request access log filled the buffer -- about 4KB on
    Windows -- and the server stopped answering partway through the suite).
    """

    def _start(self, tmp_path, monkeypatch, wait_returns=True, base_url=None):
        mock_dir = tmp_path / "elsewhere" / "mocks"
        mock_dir.mkdir(parents=True)
        (mock_dir / "dynamic_api.py").write_text("app = None\n", encoding="utf-8")

        captured: dict = {}

        class _FakePopen:
            def __init__(self, *args, **kwargs):
                captured["args"] = args
                captured["kwargs"] = kwargs

            def wait(self, timeout=None):
                return 0

            def send_signal(self, signum):
                pass

        monkeypatch.setattr(chaos.subprocess, "Popen", _FakePopen)
        monkeypatch.chdir(tmp_path)

        breaker = chaos.EnhancedChaosBreaker(
            mock_dir=str(mock_dir), base_url=base_url or "http://localhost:8000",
        )
        monkeypatch.setattr(breaker, "_wait_for_server", lambda: wait_returns)
        return breaker, captured, mock_dir

    def test_the_mock_parent_directory_reaches_the_child(self, tmp_path, monkeypatch):
        breaker, captured, mock_dir = self._start(tmp_path, monkeypatch)
        assert breaker.start_mock_server() is True

        env = captured["kwargs"]["env"]
        assert str(mock_dir.resolve().parent) in env["PYTHONPATH"].split(os.pathsep)

    def test_the_spawned_server_listens_on_the_base_url_port(self, tmp_path, monkeypatch):
        # --base-url with another port used to spawn the server on 8000
        # anyway, so the health check polled a port nothing was listening on
        # and the suite aborted once its timeout ran out.
        breaker, captured, _ = self._start(
            tmp_path, monkeypatch, base_url="http://127.0.0.1:9123",
        )
        assert breaker.start_mock_server() is True

        argv = captured["args"][0]
        assert argv[argv.index("--port") + 1] == "9123"

    def test_child_output_is_not_an_undrained_pipe(self, tmp_path, monkeypatch):
        breaker, captured, _ = self._start(tmp_path, monkeypatch)
        breaker.start_mock_server()
        try:
            assert captured["kwargs"]["stdout"] != chaos.subprocess.PIPE
            assert captured["kwargs"]["stderr"] == chaos.subprocess.STDOUT
        finally:
            breaker.stop_mock_server()

    def test_a_failed_start_stops_the_server_it_spawned(self, tmp_path, monkeypatch):
        # An abandoned server keeps holding the port, so every later run fails
        # to bind until it is killed by hand.
        breaker, _, _ = self._start(tmp_path, monkeypatch, wait_returns=False)
        stopped: list = []
        monkeypatch.setattr(breaker, "stop_mock_server", lambda: stopped.append(True))

        assert breaker.start_mock_server() is False
        assert stopped == [True]
