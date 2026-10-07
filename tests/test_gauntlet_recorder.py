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


class _StubRawHeaders:
    def __init__(self, pairs):
        self._pairs = pairs

    def items(self):
        return iter(self._pairs)


class _StubResponse:
    """Stands in for responses.Response without a live server."""

    def __init__(self, status_code=200, text="", headers=None, raw_pairs=None):
        self.status_code = status_code
        self.text = text
        self.headers = headers or {}
        self.raw = type("Raw", (), {"headers": _StubRawHeaders(raw_pairs or [])})()


class TestResponseFidelity:
    """What the recorder writes must be what the origin sent.

    The response status, headers and content type used to be hardcoded to a
    200 and application/json, so a captured redirect lost its Location, a
    captured login lost its cookies, and a non-JSON body was described as
    JSON and re-encoded into a quoted string.
    """

    def test_the_status_comes_from_the_response(self):
        entry = _make_recorder().record_request(
            "POST", "http://localhost:9000/checkout",
            response=_StubResponse(status_code=400, text='{"error": "nope"}'),
        )
        assert entry["response"]["status"] == 400

    def test_the_response_headers_and_type_are_recorded(self):
        response = _StubResponse(
            text="plain body",
            headers={"Content-Type": "text/plain; charset=utf-8"},
            raw_pairs=[("Content-Type", "text/plain; charset=utf-8")],
        )
        entry = _make_recorder().record_request(
            "GET", "http://localhost:9000/x", response=response,
        )
        assert entry["response"]["headers"] == [
            {"name": "Content-Type", "value": "text/plain; charset=utf-8"},
        ]
        assert entry["response"]["content"]["mimeType"] == "text/plain; charset=utf-8"

    def test_repeated_set_cookie_lines_are_kept_apart(self):
        # requests' mapping joins them with a comma, which cannot be undone:
        # an Expires attribute contains commas of its own.
        pairs = [
            ("Set-Cookie", "sid=abc; Path=/"),
            ("Set-Cookie", "csrf=zzz; Path=/; Expires=Wed, 21 Oct 2026 07:28:00 GMT"),
        ]
        response = _StubResponse(
            headers={"Set-Cookie": "sid=abc; Path=/, csrf=zzz; Path=/; Expires=..."},
            raw_pairs=pairs,
        )
        entry = _make_recorder().record_request(
            "GET", "http://localhost:9000/x", response=response,
        )
        assert [h["value"] for h in entry["response"]["headers"]] == [
            "sid=abc; Path=/",
            "csrf=zzz; Path=/; Expires=Wed, 21 Oct 2026 07:28:00 GMT",
        ]

    def test_a_non_json_body_is_recorded_verbatim(self):
        # It used to go through json.dumps and land in the archive quoted.
        response = _StubResponse(
            text="plain body",
            headers={"Content-Type": "text/plain"},
            raw_pairs=[("Content-Type", "text/plain")],
        )
        entry = _make_recorder().record_request(
            "GET", "http://localhost:9000/x", response=response,
        )
        assert entry["response"]["content"]["text"] == "plain body"

    def test_the_older_call_shape_still_works(self):
        entry = _make_recorder().record_request(
            "GET", "http://localhost:9000/products",
            response_data={"items": []},
        )
        assert entry["response"]["content"]["mimeType"] == "application/json"
        assert entry["response"]["content"]["text"] == '{"items": []}'
        assert entry["response"]["headers"] == []
