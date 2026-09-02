"""
MockClaw LLM Client Manager Tests
Covers the retry/backoff logic in LLMClientManager.call_with_retry.
"""

import importlib
import sys
import time
import types

import pytest

import core.llm_client_manager as llm_client_manager
from core.llm_client_manager import LLMClientManager


class TestCallWithRetry:
    def test_returns_result_without_retry(self):
        manager = LLMClientManager(max_retries=3)
        assert manager.call_with_retry(lambda **kw: "done", model="m") == "done"

    def test_retries_transient_then_raises(self, monkeypatch):
        manager = LLMClientManager(max_retries=3, retry_delay=1.0)

        sleeps: list[float] = []
        monkeypatch.setattr(time, "sleep", sleeps.append)
        calls = {"n": 0}

        def flaky(**kwargs):
            calls["n"] += 1
            raise ConnectionError("network down")

        with pytest.raises(ConnectionError):
            manager.call_with_retry(flaky, model="m")

        assert calls["n"] == 3
        # Exponential backoff: 1.0s then 2.0s between the three attempts.
        assert sleeps == [1.0, 2.0]

    def test_succeeds_after_transient_retries(self, monkeypatch):
        manager = LLMClientManager(max_retries=3, retry_delay=1.0)
        monkeypatch.setattr(time, "sleep", lambda s: None)
        calls = {"n": 0}

        def flaky(**kwargs):
            calls["n"] += 1
            if calls["n"] < 3:
                raise OSError("socket reset")
            return "recovered"

        assert manager.call_with_retry(flaky, model="m") == "recovered"
        assert calls["n"] == 3

    def test_does_not_retry_non_transient(self):
        manager = LLMClientManager(max_retries=3)
        calls = {"n": 0}

        def bad(**kwargs):
            calls["n"] += 1
            raise ValueError("bad request")

        with pytest.raises(ValueError):
            manager.call_with_retry(bad, model="m")

        assert calls["n"] == 1


class TestTransientErrorTypes:
    def test_openai_network_errors_join_transient_set(self):
        """APIConnectionError/APITimeoutError must be retried, not re-raised."""
        fake_openai = types.ModuleType("openai")

        class FakeAPIConnectionError(Exception):
            pass

        class FakeAPITimeoutError(Exception):
            pass

        fake_openai.APIConnectionError = FakeAPIConnectionError
        fake_openai.APITimeoutError = FakeAPITimeoutError

        had_openai = "openai" in sys.modules
        saved = sys.modules.get("openai")
        sys.modules["openai"] = fake_openai
        try:
            reloaded = importlib.reload(llm_client_manager)
            assert FakeAPIConnectionError in reloaded._TRANSIENT_ERROR_TYPES
            assert FakeAPITimeoutError in reloaded._TRANSIENT_ERROR_TYPES
        finally:
            if had_openai:
                sys.modules["openai"] = saved
            else:
                sys.modules.pop("openai", None)
            importlib.reload(llm_client_manager)
