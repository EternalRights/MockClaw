"""
MockClaw Test Configuration and Helpers
S2-007: Test Helpers for CLI and Smart Fallback Testing
"""

import asyncio
import json
import time
from pathlib import Path
from typing import Any, Dict, Generator, Optional
from contextlib import contextmanager

import pytest
import httpx
from fastapi.testclient import TestClient


# Test fixtures directory
TEST_DATA_DIR = Path(__file__).parent / "test_data"
GAUNTLET_DIR = Path(__file__).parent / "gauntlet"


class MockServerTracker:
    """
    Tracks requests made to mock server for verification.
    Used by verify_endpoint_called() and get_last_request_body().
    """
    def __init__(self):
        self.request_history: Dict[str, list] = {}
    
    def record_request(self, endpoint: str, method: str, body: Optional[Dict] = None):
        """Record a request made to an endpoint."""
        if endpoint not in self.request_history:
            self.request_history[endpoint] = []
        
        self.request_history[endpoint].append({
            "method": method,
            "body": body,
            "timestamp": time.time()
        })
    
    def get_call_count(self, endpoint: str) -> int:
        """Get number of times an endpoint was called."""
        return len(self.request_history.get(endpoint, []))
    
    def get_last_request_body(self, endpoint: str) -> Optional[Dict]:
        """Get the body of the last request to an endpoint."""
        history = self.request_history.get(endpoint, [])
        if history:
            return history[-1].get("body")
        return None
    
    def clear(self):
        """Clear all request history."""
        self.request_history.clear()


# Global tracker instance
_tracker = MockServerTracker()


def verify_endpoint_called(endpoint: str, times: int = 1) -> bool:
    """
    Verify that a mock endpoint was called the expected number of times.
    
    Args:
        endpoint: The endpoint path (e.g., "/checkout")
        times: Expected number of calls (default: 1)
    
    Returns:
        True if endpoint was called expected times
    
    Raises:
        AssertionError: If call count doesn't match expected
    """
    actual_count = _tracker.get_call_count(endpoint)
    assert actual_count == times, (
        f"Endpoint {endpoint} was called {actual_count} times, "
        f"expected {times} times"
    )
    return True


def get_last_request_body(endpoint: str) -> Optional[Dict]:
    """
    Get the JSON body of the last request to an endpoint.
    
    Args:
        endpoint: The endpoint path (e.g., "/checkout")
    
    Returns:
        The request body as a dict, or None if no requests
    
    Example:
        >>> body = get_last_request_body("/checkout")
        >>> assert body["coupon_code"] == "EXPIRED2026"
    """
    return _tracker.get_last_request_body(endpoint)


def clear_tracker():
    """Clear the request tracker between tests."""
    _tracker.clear()


@pytest.fixture
def tracker():
    """Provide access to the request tracker."""
    return _tracker


@pytest.fixture
def sample_har_path() -> Path:
    """Path to the sample HAR file from gauntlet."""
    har_path = GAUNTLET_DIR / "flow.har"
    if not har_path.exists():
        pytest.skip(f"HAR file not found at {har_path}")
    return har_path


@pytest.fixture
def temp_output_dir(tmp_path: Path) -> Path:
    """Create a temporary directory for generated mocks."""
    output_dir = tmp_path / "generated_mocks"
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir


@pytest.fixture
def no_llm_env(monkeypatch):
    """Set environment to disable LLM for testing."""
    monkeypatch.setenv("LLM_PROVIDER", "none")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    return monkeypatch


@contextmanager
def mock_server_context(app) -> Generator[TestClient, None, None]:
    """
    Context manager for running mock server tests.
    Tracks all requests made to the server.
    
    Args:
        app: FastAPI application instance
    
    Yields:
        TestClient instance for making requests
    
    Example:
        with mock_server_context(app) as client:
            response = client.post("/checkout", json={"coupon": "EXPIRED2026"})
            assert response.status_code == 400
    """
    # Clear tracker before test
    clear_tracker()
    
    # Create middleware to track requests
    @app.middleware("http")
    async def track_requests(request, call_next):
        body = None
        try:
            body = await request.json()
        except Exception:
            pass
        
        _tracker.record_request(
            endpoint=request.url.path,
            method=request.method,
            body=body
        )
        
        response = await call_next(request)
        return response
    
    client = TestClient(app)
    try:
        yield client
    finally:
        pass


@pytest.fixture
def mock_client(app):
    """
    Create a test client that tracks requests.
    
    Usage:
        def test_checkout(mock_client):
            response = mock_client.post("/checkout", json={"coupon": "EXPIRED2026"})
            assert response.status_code == 400
            verify_endpoint_called("/checkout", times=1)
    """
    clear_tracker()
    
    # Add tracking middleware if not already present
    if not any(hasattr(m, '__name__') and m.__name__ == 'track_requests' 
               for m in app.middleware_stack.middlewares if hasattr(m, '__name__')):
        
        @app.middleware("http")
        async def track_requests(request, call_next):
            body = None
            try:
                body = await request.json()
            except Exception:
                pass
            
            _tracker.record_request(
                endpoint=request.url.path,
                method=request.method,
                body=body
            )
            
            response = await call_next(request)
            return response
    
    with TestClient(app) as client:
        yield client


@pytest.fixture
def checkout_request_body() -> Dict[str, Any]:
    """Sample checkout request body for testing."""
    return {
        "user_id": "user123",
        "coupon_code": "EXPIRED2026",
        "shipping_address": "123 Main St"
    }


@pytest.fixture
def valid_checkout_body() -> Dict[str, Any]:
    """Sample valid checkout request body."""
    return {
        "user_id": "user123",
        "coupon_code": "SAVE10",
        "shipping_address": "123 Main St"
    }


@pytest.fixture
def no_coupon_body() -> Dict[str, Any]:
    """Checkout request with no coupon."""
    return {
        "user_id": "user123",
        "shipping_address": "123 Main St"
    }


# Helper functions for async tests
async def async_wait_for_server(url: str, timeout: float = 5.0) -> bool:
    """Wait for server to be ready."""
    start = time.time()
    async with httpx.AsyncClient() as client:
        while time.time() - start < timeout:
            try:
                response = await client.get(f"{url}/health")
                if response.status_code == 200:
                    return True
            except Exception:
                pass
            await asyncio.sleep(0.1)
    return False


# Pytest configuration
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test (requires server)"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )
    config.addinivalue_line(
        "markers", "llm: mark test as requiring LLM API key"
    )
