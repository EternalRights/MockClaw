"""
Gauntlet recorder tests.

Covers the pure record_request logic (query-string extraction and HAR
entry shape) without needing a running Dummy Shop server.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from gauntlet_recorder import GauntletRecorder  # noqa: E402


def _make_recorder():
    return GauntletRecorder(base_url="http://localhost:9000")


def test_record_request_extracts_query_params():
    recorder = _make_recorder()
    entry = recorder.record_request(
        "GET",
        "http://localhost:9000/products?category=electronics&page=2",
        response_data={"items": []},
    )
    qs = {p["name"]: p["value"] for p in entry["request"]["queryString"]}
    assert qs == {"category": "electronics", "page": "2"}


def test_record_request_no_query_params():
    recorder = _make_recorder()
    entry = recorder.record_request(
        "GET",
        "http://localhost:9000/products",
        response_data={"items": []},
    )
    assert entry["request"]["queryString"] == []


def test_record_request_sets_post_data():
    recorder = _make_recorder()
    body = {"username": "testuser", "password": "secret"}
    entry = recorder.record_request(
        "POST",
        "http://localhost:9000/login",
        request_data=body,
        response_data={"token": "abc"},
    )
    assert entry["request"]["postData"] is not None
    assert entry["request"]["postData"]["mimeType"] == "application/json"
    assert "testuser" in entry["request"]["postData"]["text"]


def test_record_request_error_response():
    recorder = _make_recorder()
    entry = recorder.record_request(
        "POST",
        "http://localhost:9000/checkout",
        request_data={"coupon_code": "EXPIRED2026"},
        response_data=None,
        status_code=400,
        error="COUPON_EXPIRED",
    )
    assert entry["response"]["status"] == 400
    assert "COUPON_EXPIRED" in entry["response"]["content"]["text"]
