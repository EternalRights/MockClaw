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


class TestParseJunkMethodIsolation:
    """A syntactically invalid method must not 500 the whole upload.

    RFC 7230 says a method is a token (no spaces, slashes, parens). A HAR
    carrying one such entry used to blow up the entire /parse request:
    EndpointInfo's validator raised, the exception escaped the endpoint
    loop, and every valid entry died with it.
    """

    def test_one_junk_method_among_valid_entries(self, client):
        resp = _upload(client, "mixed.har", _har([
            _entry("GET WITH SPACE", "https://api.example.com/junk"),
            _entry("GET", "https://api.example.com/good1"),
            _entry("POST", "https://api.example.com/good2"),
        ]))
        assert resp.status_code == 200, resp.text
        body = resp.json()
        paths = [e["path"] for e in body["endpoints"]]
        # Good entries survive either way; the junk one is downgraded to GET
        # by the parser, so all three appear.
        assert "/good1" in paths and "/good2" in paths
        assert body["total_endpoints"] == 3
        assert body["skipped"] == []

    @pytest.mark.parametrize("method", ["GET/POST", "GE(T", "GET\t"])
    def test_parser_downgrades_token_violations_to_get(self, client, method):
        # The CLI path has no EndpointInfo safety net: without the parser
        # fallback, generate would emit api_route(methods=["GET/POST"]),
        # a route no real client can ever hit.
        resp = _upload(client, "junk.har", _har([
            _entry(method, "https://api.example.com/junk"),
        ]))
        assert resp.status_code == 200, resp.text
        assert resp.json()["endpoints"][0]["method"] == "GET"

    @pytest.mark.parametrize("method", ["PROPFIND", "MKCOL", "123", "X-CUSTOM"])
    def test_token_shaped_methods_pass_through(self, client, method):
        # The fallback must not overreach: numeric and custom-but-legal
        # tokens keep their recorded method.
        resp = _upload(client, "token.har", _har([
            _entry(method, "https://api.example.com/x"),
        ]))
        assert resp.status_code == 200, resp.text
        assert resp.json()["endpoints"][0]["method"] == method

    def test_junk_method_generated_mock_still_importable(self, tmp_path):
        # End-to-end through the CLI-side generator: the downgraded entry
        # must produce a mock file that imports and serves traffic.
        import importlib.util

        from core.generator import MockGenerator
        from core.parser import HARParser

        har_path = tmp_path / "junk.har"
        har_path.write_text(_har([
            _entry("GET WITH SPACE", "https://api.example.com/junk"),
            _entry("GET", "https://api.example.com/ok"),
        ]).decode(), encoding="utf-8")

        data = HARParser(str(har_path)).export_as_dict()
        out_dir = tmp_path / "mocks"
        results = MockGenerator(use_smart_fallback=False).generate_all(
            data["endpoints"], str(out_dir),
        )
        assert all(r.success for r in results), [r.error for r in results]

        mock_file = out_dir / "dynamic_api.py"
        spec = importlib.util.spec_from_file_location("dyn", str(mock_file))
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)  # must not raise

        with TestClient(mod.app) as c:
            ok = c.get("/ok")
            assert ok.status_code == 200, ok.text
            junk = c.get("/junk")  # downgraded to GET, so a plain GET hits it
            assert junk.status_code == 200, junk.text

    def test_skipped_reports_direct_endpoint_violations(self, client, monkeypatch):
        # The parser fallback handles junk methods, but the per-entry
        # try/except in /parse must stay: any other EndpointInfo violation
        # (a non-string path sneaking through, say) has to surface in
        # `skipped` instead of 500-ing the upload.
        payload = _har([
            _entry("GET", "https://api.example.com/a"),
            _entry("GET", "https://api.example.com/b"),
        ])
        original = brain.EndpointInfo

        # A real ValidationError from a genuinely invalid model, reused as
        # the poison: faking pydantic's internal error dicts is fragile.
        try:
            original(id="x", path=None, method="GET", status=200, generated=False)
        except brain.ValidationError as e:
            poison = e
        else:  # pragma: no cover - EndpointInfo must reject a None path
            raise AssertionError("EndpointInfo unexpectedly accepted path=None")

        # Only the second construction blows up, proving per-entry isolation.
        calls = {"n": 0}

        def _flaky(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 2:
                raise poison
            return original(*args, **kwargs)

        monkeypatch.setattr(brain, "EndpointInfo", _flaky)
        resp = _upload(client, "poison.har", payload)
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_endpoints"] == 1
        assert "/a" in [e["path"] for e in body["endpoints"]]
        assert len(body["skipped"]) == 1
        assert "path" in body["skipped"][0]


class TestGenerateResponseShape:
    """One endpoint, one response shape.

    A second /generate used to answer with only success/endpoint_id/cached/
    message, so a client that read generated_code or logs after a cache hit
    got nothing -- although the code is stored on the endpoint it kept.
    """

    def _generate_twice(self, client):
        resp = _upload(client, "one.har", _har([
            _entry("GET", "https://api.example.com/api/x"),
        ]))
        endpoint_id = resp.json()["endpoints"][0]["id"]

        first = client.post("/generate", json={"endpoint_id": endpoint_id}).json()
        second = client.post("/generate", json={"endpoint_id": endpoint_id}).json()
        return first, second

    def test_a_cache_hit_has_every_key_a_fresh_one_has(self, client):
        first, second = self._generate_twice(client)

        assert first["cached"] is False
        assert second["cached"] is True
        assert set(first) <= set(second), sorted(set(first) - set(second))

    def test_a_cache_hit_carries_the_same_code(self, client):
        first, second = self._generate_twice(client)

        assert first["generated_code"]
        assert second["generated_code"] == first["generated_code"]

    def test_a_cache_hit_still_reports_logs_and_no_error(self, client):
        _, second = self._generate_twice(client)

        assert second["logs"]
        assert second["error"] is None


class _StubGenerator:
    """Stand-in for the generator, so a failure is deterministic."""

    def __init__(self, fail: bool) -> None:
        self._fail = fail

    def generate_endpoint(self, endpoint_data):
        from core.generator import GenerationResult

        path = endpoint_data.get("resource_path", "")
        if self._fail:
            return GenerationResult(False, "", path, error="stub failure")
        return GenerationResult(True, "@app.get('/x')\nasync def x():\n    return {}\n", path)


class TestStatsFailures:
    """The failure count is a statistic, not a view of the log panel.

    It used to be counted from the log buffer, which is bounded and which the
    dashboard can clear: clearing the logs reported zero failed generations,
    and failures older than the last 1000 log entries were never counted.
    """

    def _register_one_endpoint(self, client) -> str:
        resp = _upload(client, "one.har", _har([
            _entry("GET", "https://api.example.com/api/x"),
        ]))
        assert resp.status_code == 200, resp.text
        return resp.json()["endpoints"][0]["id"]

    def test_a_failed_generation_is_counted(self, client, monkeypatch):
        endpoint_id = self._register_one_endpoint(client)
        monkeypatch.setattr(brain.app_state, "_generator", _StubGenerator(fail=True))

        resp = client.post("/generate", json={"endpoint_id": endpoint_id})
        assert resp.status_code == 200, resp.text
        assert resp.json()["success"] is False

        stats = client.get("/stats").json()
        assert stats["failures"] == 1
        assert stats["generated"] == 0
        assert stats["pending"] == 1

    def test_clearing_the_logs_keeps_the_count(self, client, monkeypatch):
        endpoint_id = self._register_one_endpoint(client)
        monkeypatch.setattr(brain.app_state, "_generator", _StubGenerator(fail=True))
        client.post("/generate", json={"endpoint_id": endpoint_id})

        assert client.delete("/logs").status_code == 200
        assert client.get("/stats").json()["failures"] == 1

    def test_a_later_success_clears_the_failure(self, client, monkeypatch):
        endpoint_id = self._register_one_endpoint(client)
        monkeypatch.setattr(brain.app_state, "_generator", _StubGenerator(fail=True))
        client.post("/generate", json={"endpoint_id": endpoint_id})
        assert client.get("/stats").json()["failures"] == 1

        monkeypatch.setattr(brain.app_state, "_generator", _StubGenerator(fail=False))
        assert client.post(
            "/generate", json={"endpoint_id": endpoint_id}
        ).json()["success"] is True

        stats = client.get("/stats").json()
        assert stats["failures"] == 0
        assert stats["generated"] == 1

    def test_uploading_a_new_archive_resets_the_count(self, client, monkeypatch):
        endpoint_id = self._register_one_endpoint(client)
        monkeypatch.setattr(brain.app_state, "_generator", _StubGenerator(fail=True))
        client.post("/generate", json={"endpoint_id": endpoint_id})
        assert client.get("/stats").json()["failures"] == 1

        self._register_one_endpoint(client)
        assert client.get("/stats").json()["failures"] == 0

    def test_deleting_the_endpoint_clears_the_failure(self, client, monkeypatch):
        endpoint_id = self._register_one_endpoint(client)
        monkeypatch.setattr(brain.app_state, "_generator", _StubGenerator(fail=True))
        client.post("/generate", json={"endpoint_id": endpoint_id})

        assert client.delete(f"/endpoints/{endpoint_id}").status_code == 200
        stats = client.get("/stats").json()
        assert stats["total_endpoints"] == 0
        assert stats["failures"] == 0
