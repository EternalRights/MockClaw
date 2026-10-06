"""
Chaos test utility tests.

Covers the pure helper functions in scripts/enhanced_chaos_test.py
(percentile calculation and millisecond formatting) which are the
deterministic, testable parts of the chaos engine.
"""

import os
import sys
from pathlib import Path

import pytest

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


class TestSpawnedMockServer:
    """How the mock server is spawned decides whether the suite can run.

    Two faults compounded: the child was never told where the mock package
    lives (so a mock dir outside the current directory died with "No module
    named 'mocks'"), and its output went to pipes nobody drained (so
    uvicorn's per-request access log filled the buffer -- about 4KB on
    Windows -- and the server stopped answering partway through the suite).
    """

    def _start(self, tmp_path, monkeypatch, wait_returns=True):
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

        breaker = chaos.EnhancedChaosBreaker(mock_dir=str(mock_dir))
        monkeypatch.setattr(breaker, "_wait_for_server", lambda: wait_returns)
        return breaker, captured, mock_dir

    def test_the_mock_parent_directory_reaches_the_child(self, tmp_path, monkeypatch):
        breaker, captured, mock_dir = self._start(tmp_path, monkeypatch)
        assert breaker.start_mock_server() is True

        env = captured["kwargs"]["env"]
        assert str(mock_dir.resolve().parent) in env["PYTHONPATH"].split(os.pathsep)

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
