"""
MockClaw Test Configuration
"""

from typing import Any

import pytest


@pytest.fixture
def minimal_har_data() -> dict[str, Any]:
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "MockClaw Test", "version": "0.1.0"},
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
                            "text": '{"token":"mock_jwt_token","user":{"id":1,"username":"testuser","email":"test@example.com"}}'
                        },
                        "redirectURL": "",
                        "headersSize": -1,
                        "bodySize": 150
                    },
                    "cache": {},
                    "timings": {"send": 0, "wait": 100, "receive": 10}
                },
                {
                    "startedDateTime": "2026-03-28T10:00:01.000Z",
                    "time": 80,
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/api/users/456?status=error",
                        "httpVersion": "HTTP/1.1",
                        "headers": [{"name": "Authorization", "value": "Bearer mock_token"}],
                        "queryString": [{"name": "status", "value": "error"}],
                        "postData": None,
                        "headersSize": -1,
                        "bodySize": 0
                    },
                    "response": {
                        "status": 500,
                        "statusText": "Internal Server Error",
                        "httpVersion": "HTTP/1.1",
                        "headers": [{"name": "Content-Type", "value": "application/json"}],
                        "content": {
                            "mimeType": "application/json",
                            "text": '{"error":"Database connection failed","code":"ERR_DB_CONNECTION"}'
                        },
                        "redirectURL": "",
                        "headersSize": -1,
                        "bodySize": 80
                    },
                    "cache": {},
                    "timings": {"send": 0, "wait": 60, "receive": 10}
                }
            ]
        }
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
