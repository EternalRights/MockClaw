"""Pytest configuration for async tests."""
import pytest

# Configure pytest-asyncio to use auto mode
pytest_plugins = ('pytest_asyncio',)

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "asyncio: mark test as an asyncio test."
    )
