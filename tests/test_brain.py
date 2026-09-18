"""
MockClaw Brain Backend Tests

Covers the input handling of the dashboard backend: the /parse upload path
has to survive real-world HAR captures, and the configured log format has
to be renderable.
"""

import io
import json
import logging

import pytest
from fastapi.testclient import TestClient

import brain


@pytest.fixture
def client():
    with TestClient(brain.app) as c:
        yield c


def _har(entries):
    return json.dumps({"log": {"version": "1.2", "entries": entries}}).encode()


def _entry(method, url, status=200, body='{"ok": true}'):
    return {
        "request": {"method": method, "url": url, "headers": [], "queryString": []},
        "response": {
            "status": status,
            "headers": [],
            "content": {"mimeType": "application/json", "text": body},
        },
        "time": 10,
    }


def _upload(client, filename, payload):
    return client.post(
        "/parse",
        files={"file": (filename, io.BytesIO(payload), "application/json")},
    )


class TestLogFormat:
    """The configured log format must actually render."""

    def test_format_renders_a_record(self):
        # A missing conversion character ('%(levelname)' instead of
        # '%(levelname)s') makes every log call raise ValueError inside the
        # formatter, so nothing is ever logged.
        record = logging.LogRecord(
            name="brain", level=logging.INFO, pathname=__file__, lineno=1,
            msg="hello", args=(), exc_info=None,
        )
        rendered = logging.Formatter(brain._LOG_FORMAT).format(record)
        assert "hello" in rendered
        assert "INFO" in rendered

    def test_format_has_conversion_for_every_field(self):
        import re

        placeholders = re.findall(r"%\((\w+)\)(.)?", brain._LOG_FORMAT)
        assert placeholders, "expected mapping-style placeholders"
        missing = [name for name, conv in placeholders if conv != "s"]
        assert not missing, f"placeholders without a conversion char: {missing}"


class TestParseMethodHandling:
    """One unusual entry must not fail the whole upload."""

    def test_standard_methods(self, client):
        resp = _upload(client, "ok.har", _har([
            _entry("GET", "https://api.example.com/a"),
            _entry("POST", "https://api.example.com/b"),
        ]))
        assert resp.status_code == 200, resp.text
        assert resp.json()["total_endpoints"] == 2

    def test_webdav_method_is_accepted(self, client):
        # WebDAV methods used to fail EndpointInfo validation, which turned
        # the whole /parse request into a 500 instead of listing the route.
        resp = _upload(client, "dav.har", _har([
            _entry("GET", "https://api.example.com/a"),
            _entry("PROPFIND", "https://api.example.com/dav"),
        ]))
        assert resp.status_code == 200, resp.text
        methods = [e["method"] for e in resp.json()["endpoints"]]
        assert methods == ["GET", "PROPFIND"]

    @pytest.mark.parametrize("method", ["TRACE", "CONNECT", "MKCOL", "propfind"])
    def test_unusual_methods_are_accepted(self, client, method):
        resp = _upload(client, "x.har", _har([
            _entry(method, "https://api.example.com/x"),
        ]))
        assert resp.status_code == 200, resp.text
        assert resp.json()["endpoints"][0]["method"] == method.upper()

    def test_extension_check_ignores_case(self, client):
        payload = _har([_entry("GET", "https://api.example.com/a")])
        for name in ["export.har", "export.HAR", "export.Har"]:
            resp = _upload(client, name, payload)
            assert resp.status_code == 200, f"{name} -> {resp.text}"

    def test_non_har_extension_is_still_rejected(self, client):
        payload = _har([_entry("GET", "https://api.example.com/a")])
        resp = _upload(client, "export.json", payload)
        assert resp.status_code == 400
