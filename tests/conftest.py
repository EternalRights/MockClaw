"""
MockClaw Test Configuration
"""

import sys
from pathlib import Path
from typing import Any, Dict, Optional

import pytest


TEST_DATA_DIR = Path(__file__).parent / "test_data"
GAUNTLET_DIR = Path(__file__).parent / "gauntlet"


@pytest.fixture
def sample_har_path() -> Path:
    har_path = GAUNTLET_DIR / "flow.har"
    if not har_path.exists():
        pytest.skip(f"HAR file not found at {har_path}")
    return har_path


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    output_dir = tmp_path / "generated_mocks"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def no_llm_env(monkeypatch):
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    return monkeypatch


@pytest.fixture
def checkout_request_body() -> Dict[str, Any]:
    return {
        "user_id": "user123",
        "coupon_code": "EXPIRED2026",
        "shipping_address": "123 Main St"
    }


@pytest.fixture
def valid_checkout_body() -> Dict[str, Any]:
    return {
        "user_id": "user123",
        "coupon_code": "SAVE10",
        "shipping_address": "123 Main St"
    }


@pytest.fixture
def no_coupon_body() -> Dict[str, Any]:
    return {
        "user_id": "user123",
        "shipping_address": "123 Main St"
    }


def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires server)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "llm: mark test as requiring LLM API key"
    )
