"""
MockClaw Generation Tests
"""

import json

import pytest

from core.parser import HARParser
from core.generator import MockGenerator, GenerationResult
from core.route_builder import build_route, generate_func_name, body_literal
from core.code_extractor import CodeExtractor


def test_har_parser(tmp_path, minimal_har_data):
    test_file = tmp_path / "test.har"
    test_file.write_text(json.dumps(minimal_har_data), encoding="utf-8")

    parser = HARParser(str(test_file))
    endpoints = parser.get_endpoints()

    assert len(endpoints) == 2, f"Expected 2 endpoints, got {len(endpoints)}"

    login_ep = next(e for e in endpoints if "login" in e.resource_path)
    assert login_ep.method == "POST"
    assert len(login_ep.responses) == 1
    assert login_ep.responses[0].status == 200

    users_ep = next(e for e in endpoints if "users" in e.resource_path)
    assert users_ep.method == "GET"
    assert len(users_ep.responses) == 1
    assert users_ep.responses[0].status == 500


def test_generator(tmp_path, minimal_har_data):
    test_file = tmp_path / "test.har"
    test_file.write_text(json.dumps(minimal_har_data), encoding="utf-8")

    parser = HARParser(str(test_file))
    endpoints_data = parser.export_as_dict()

    output_dir = tmp_path / "generated_mocks"
    generator = MockGenerator(use_smart_fallback=True)
    results = generator.generate_all(
        endpoints_data["endpoints"],
        str(output_dir),
        use_smart_fallback=True,
    )

    assert len(results) >= 1, "Should generate at least 1 endpoint"
    assert all(r.success for r in results), f"All endpoints should succeed: {[r.error for r in results]}"

    generated_file = output_dir / "dynamic_api.py"
    assert generated_file.exists(), "Generated file should exist"

    content = generated_file.read_text(encoding="utf-8")
    assert "from fastapi import" in content, "Should import FastAPI"
    assert "app = FastAPI" in content, "Should create FastAPI app"
    assert "/health" in content, "Should include /health endpoint"


def test_generated_code_is_valid_python(tmp_path, minimal_har_data):
    test_file = tmp_path / "test.har"
    test_file.write_text(json.dumps(minimal_har_data), encoding="utf-8")

    parser = HARParser(str(test_file))
    endpoints_data = parser.export_as_dict()

    output_dir = tmp_path / "generated_mocks"
    generator = MockGenerator(use_smart_fallback=True)
    generator.generate_all(endpoints_data["endpoints"], str(output_dir))

    content = (output_dir / "dynamic_api.py").read_text(encoding="utf-8")
    compile(content, "dynamic_api.py", "exec")


def test_smart_fallback_generic():
    responses = [
        {"request": {"body": '{"role": "admin", "name": "Alice"}'}, "status": 200, "body": '{"access": "full"}'},
        {"request": {"body": '{"role": "user", "name": "Bob"}'}, "status": 200, "body": '{"access": "limited"}'},
        {"request": {"body": '{"role": "guest", "name": "Charlie"}'}, "status": 403, "body": '{"error": "Forbidden"}'},
    ]

    route_code = build_route("POST", "/api/data", responses, "post__api_data", use_smart_fallback=True)

    assert 'body.get("role")' in route_code, "Should auto-detect 'role' as routing field"
    assert 'if body.get("role") == "admin"' in route_code
    assert 'elif body.get("role") == "user"' in route_code
    assert 'elif body.get("role") == "guest"' in route_code


def test_smart_fallback_no_differing_fields():
    responses = [
        {"request": {"body": '{"type": "A"}'}, "status": 200, "body": '{"ok": true}'},
        {"request": {"body": '{"type": "A"}'}, "status": 200, "body": '{"ok": true}'},
    ]

    route_code = build_route("POST", "/api/same", responses, "post__api_same", use_smart_fallback=True)
    assert "elif" not in route_code, "Should fall back when no differing fields"
    assert "@app.post" in route_code, "Should still generate a valid route"


class TestSmartRouteMultiField:
    """Single-field routing is not enough when a secondary field differs."""

    def test_two_fields_joined_with_and(self):
        # No single field separates all three responses: role can tell
        # admin from user but not us from eu, region the opposite. Both
        # are needed, so the generated conditions must join them with and.
        responses = [
            {"request": {"body": '{"role": "admin", "region": "us"}'}, "status": 200, "body": '{"tier": "us"}'},
            {"request": {"body": '{"role": "admin", "region": "eu"}'}, "status": 200, "body": '{"tier": "eu"}'},
            {"request": {"body": '{"role": "user", "region": "us"}'}, "status": 200, "body": '{"tier": "basic"}'},
        ]
        route = build_route("POST", "/api/perm", responses, "post_api_perm", use_smart_fallback=True)
        assert " and " in route
        assert 'body.get("role")' in route
        assert 'body.get("region")' in route
        compile(route, "<route>", "exec")

    def test_single_field_still_used_when_enough(self):
        responses = [
            {"request": {"body": '{"role": "admin", "region": "us"}'}, "status": 200, "body": '{"a": 1}'},
            {"request": {"body": '{"role": "user", "region": "us"}'}, "status": 200, "body": '{"b": 2}'},
        ]
        route = build_route("POST", "/api/role", responses, "post_api_role", use_smart_fallback=True)
        assert " and " not in route
        assert 'body.get("role")' in route

    def test_distinct_bodies_collapse_to_one_branch(self):
        responses = [
            {"request": {"body": '{"id": 1}'}, "status": 200, "body": '{"ok": 1}'},
            {"request": {"body": '{"id": 1}'}, "status": 200, "body": '{"ok": 1}'},
        ]
        route = build_route("POST", "/api/dup", responses, "post_api_dup", use_smart_fallback=True)
        assert "elif" not in route


def test_health_endpoints_in_generated_code(tmp_path, minimal_har_data):
    test_file = tmp_path / "test.har"
    test_file.write_text(json.dumps(minimal_har_data), encoding="utf-8")

    parser = HARParser(str(test_file))
    endpoints_data = parser.export_as_dict()

    output_dir = tmp_path / "generated_mocks"
    generator = MockGenerator()
    generator.generate_all(endpoints_data["endpoints"], str(output_dir))

    content = (output_dir / "dynamic_api.py").read_text(encoding="utf-8")
    assert "/health" in content
    assert "/mockclaw/info" in content
    assert "PathTraversalMiddleware" in content
    assert "RateLimitMiddleware" in content


def test_generate_func_name_sanitizes_special_chars():
    assert generate_func_name("GET", "/api/v1.0/users") == "get_api_v1_0_users"
    assert generate_func_name("POST", "/api/user-profile") == "post_api_user_profile"
    assert generate_func_name("DELETE", "/api/items/{id}") == "delete_api_items_id"
    assert generate_func_name("GET", "/").isidentifier()
    fn = generate_func_name("GET", "/api/v2.1/beta-test")
    assert fn.isidentifier(), f"'{fn}' is not a valid Python identifier"


class TestInputValidation:
    """Tests for MockGenerator input validation."""

    def test_validate_missing_resource_path(self):
        generator = MockGenerator()
        result = generator.generate_endpoint({"method": "GET"})
        assert not result.success
        assert "resource_path" in result.error.lower()

    def test_validate_missing_method(self):
        generator = MockGenerator()
        result = generator.generate_endpoint({"resource_path": "/api/test"})
        assert not result.success
        assert "method" in result.error.lower()

    def test_validate_empty_method(self):
        generator = MockGenerator()
        result = generator.generate_endpoint({
            "resource_path": "/api/test",
            "method": ""
        })
        assert not result.success
        assert "non-empty string" in result.error.lower()

    def test_validate_empty_resource_path(self):
        generator = MockGenerator()
        result = generator.generate_endpoint({
            "resource_path": "",
            "method": "GET"
        })
        assert not result.success
        assert "resource_path" in result.error.lower()
        assert "non-empty string" in result.error.lower()

    def test_validate_non_dict_input(self):
        generator = MockGenerator()
        result = generator.generate_endpoint("not_a_dict")
        assert not result.success
        assert "dict" in result.error.lower()


class TestEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def test_generate_all_empty_list(self, tmp_path):
        generator = MockGenerator()
        output_dir = tmp_path / "empty_mocks"
        results = generator.generate_all([], str(output_dir))
        assert results == []
        assert not (output_dir / "dynamic_api.py").exists()

    def test_generate_all_with_builtin_paths_only(self, tmp_path):
        generator = MockGenerator()
        output_dir = tmp_path / "builtin_mocks"
        results = generator.generate_all([
            {"resource_path": "/health", "method": "GET"},
            {"resource_path": "/mockclaw/info", "method": "GET"}
        ], str(output_dir))
        assert len(results) == 0
        assert (output_dir / "dynamic_api.py").exists()

    def test_generation_result_attributes(self):
        result = GenerationResult(
            success=True,
            generated_code="test code",
            endpoint_path="/api/test",
        )
        assert result.success is True
        assert result.generated_code == "test code"
        assert result.endpoint_path == "/api/test"
        assert result.error is None

        failed_result = GenerationResult(
            success=False,
            generated_code="",
            endpoint_path="/api/fail",
            error="Test error"
        )
        assert failed_result.success is False
        assert failed_result.error == "Test error"

    def test_smart_fallback_multiple_differing_fields(self):
        responses = [
            {"request": {"body": '{"type": "A", "category": "x"}'}, "status": 200, "body": '{"result": 1}'},
            {"request": {"body": '{"type": "B", "category": "y"}'}, "status": 201, "body": '{"result": 2}'},
        ]
        route_code = build_route("POST", "/api/multi", responses, "post__api_multi", use_smart_fallback=True)
        assert "@app.post" in route_code
        assert "if" in route_code or "return" in route_code


class TestBodyLiteral:
    """Tests for the body_literal utility function."""

    def test_valid_json_compact(self):
        result = body_literal('{"key": "value", "num": 1}')
        parsed = json.loads(result)
        assert parsed == {"key": "value", "num": 1}

    def test_nested_json(self):
        result = body_literal('{"user": {"name": "Alice", "age": 30}}')
        parsed = json.loads(result)
        assert parsed["user"]["name"] == "Alice"

    def test_json_array(self):
        result = body_literal('[{"id": 1}, {"id": 2}]')
        parsed = json.loads(result)
        assert isinstance(parsed, list)
        assert len(parsed) == 2

    def test_invalid_json_fallback(self):
        result = body_literal("not valid json")
        assert "not valid json" in result

    def test_empty_string(self):
        result = body_literal("")
        assert result is not None

    def test_null_value(self):
        result = body_literal("null")
        assert result == "null"


class TestCodeExtractor:
    """Tests for CodeExtractor — LLM response code block extraction."""

    def test_extract_python_block_with_newline(self):
        extractor = CodeExtractor()
        response = "```python\nprint('hello')\n```"
        assert extractor.extract_code(response) == "print('hello')"

    def test_extract_python_block_same_line(self):
        extractor = CodeExtractor()
        response = "```python print('hello')```"
        code = extractor.extract_code(response)
        assert "print('hello')" in code

    def test_extract_generic_block(self):
        extractor = CodeExtractor()
        response = "Here is code:\n```\ndef foo():\n    pass\n```\nDone."
        assert "def foo():" in extractor.extract_code(response)

    def test_fallback_no_blocks(self):
        extractor = CodeExtractor()
        response = "No code blocks here, just plain text."
        assert extractor.extract_code(response) == response


class TestLatencySimulation:
    """Tests for latency simulation from HAR timing data."""

    def test_parser_extracts_avg_latency(self, tmp_path, minimal_har_data):
        test_file = tmp_path / "test.har"
        test_file.write_text(json.dumps(minimal_har_data), encoding="utf-8")

        parser = HARParser(str(test_file))
        data = parser.export_as_dict()

        login = next(e for e in data["endpoints"] if "login" in e["resource_path"])
        assert login["avg_latency_ms"] == 150

        users = next(e for e in data["endpoints"] if "users" in e["resource_path"])
        assert users["avg_latency_ms"] == 80

    def test_build_route_injects_sleep(self):
        responses = [{"status": 200, "body": '{"ok": true}'}]
        route = build_route("GET", "/api/slow", responses, "get_api_slow", latency_ms=250)
        assert "await asyncio.sleep(0.250)" in route

    def test_build_route_no_latency_when_zero(self):
        responses = [{"status": 200, "body": '{"ok": true}'}]
        route = build_route("GET", "/api/fast", responses, "get_api_fast", latency_ms=0)
        assert "asyncio.sleep" not in route

    def test_smart_route_injects_sleep(self):
        responses = [
            {"request": {"body": '{"role": "admin"}'}, "status": 200, "body": '{"ok": 1}'},
            {"request": {"body": '{"role": "user"}'}, "status": 200, "body": '{"ok": 2}'},
        ]
        route = build_route("POST", "/api/check", responses, "post_api_check", use_smart_fallback=True, latency_ms=120)
        assert "await asyncio.sleep(0.120)" in route

    def test_generator_with_simulate_latency(self, tmp_path, minimal_har_data):
        test_file = tmp_path / "test.har"
        test_file.write_text(json.dumps(minimal_har_data), encoding="utf-8")

        parser = HARParser(str(test_file))
        endpoints_data = parser.export_as_dict()

        output_dir = tmp_path / "mocks"
        generator = MockGenerator(use_smart_fallback=True, simulate_latency=True)
        generator.generate_all(endpoints_data["endpoints"], str(output_dir))

        content = (output_dir / "dynamic_api.py").read_text(encoding="utf-8")
        assert "import asyncio" in content
        assert "await asyncio.sleep" in content


class TestStaticAssetFilter:
    """Tests for HARParser._is_static_asset filtering."""

    def _entry(self, url: str, mime_type: str = "application/json"):
        return {
            "request": {"url": url, "method": "GET", "headers": []},
            "response": {
                "status": 200,
                "headers": [],
                "content": {"mimeType": mime_type, "text": "{}"},
            },
        }

    def test_js_with_query_string_is_static(self):
        parser = HARParser("unused.har")
        entry = self._entry("https://example.com/app.js?ver=1.2.3")
        assert parser._is_static_asset(entry) is True

    def test_css_with_query_string_is_static(self):
        parser = HARParser("unused.har")
        entry = self._entry("https://example.com/style.css?v=42")
        assert parser._is_static_asset(entry) is True

    def test_plain_js_is_static(self):
        parser = HARParser("unused.har")
        entry = self._entry("https://example.com/static/bundle.js")
        assert parser._is_static_asset(entry) is True

    def test_api_endpoint_is_not_static(self):
        parser = HARParser("unused.har")
        entry = self._entry("https://api.example.com/v1/users")
        assert parser._is_static_asset(entry) is False

    def test_static_by_mime_type(self):
        parser = HARParser("unused.har")
        entry = self._entry("https://example.com/images/photo", mime_type="image/png")
        assert parser._is_static_asset(entry) is True


class TestDuplicateEntryCollapse:
    """Identical entries from polling/retries should collapse to one."""

    def _har(self, entries):
        return {"log": {"version": "1.2", "entries": entries}}

    def _entry(self, url, body=None, status=200, resp_body='{"ok": true}'):
        return {
            "request": {
                "method": "GET",
                "url": url,
                "headers": [],
                "queryString": [],
                "postData": (
                    {"mimeType": "application/json", "text": body}
                    if body is not None else None
                ),
            },
            "response": {
                "status": status,
                "headers": [],
                "content": {"mimeType": "application/json", "text": resp_body},
            },
        }

    def test_identical_entries_collapse(self, tmp_path):
        har = self._har([self._entry("https://api.example.com/poll")] * 5)
        f = tmp_path / "test.har"
        f.write_text(json.dumps(har), encoding="utf-8")

        endpoints = HARParser(str(f)).get_endpoints()
        assert len(endpoints) == 1
        assert len(endpoints[0].responses) == 1

    def test_same_url_different_response_kept(self, tmp_path):
        har = self._har([
            self._entry("https://api.example.com/poll", None, status=200),
            self._entry("https://api.example.com/poll", None, status=503, resp_body='{"err": 1}'),
        ])
        f = tmp_path / "test.har"
        f.write_text(json.dumps(har), encoding="utf-8")

        endpoints = HARParser(str(f)).get_endpoints()
        assert len(endpoints[0].responses) == 2

    def test_same_url_different_request_body_kept(self, tmp_path):
        entries = [
            {
                "request": {
                    "method": "POST",
                    "url": "https://api.example.com/login",
                    "headers": [],
                    "queryString": [],
                    "postData": {"mimeType": "application/json", "text": body},
                },
                "response": {
                    "status": 200,
                    "headers": [],
                    "content": {"mimeType": "application/json", "text": "{}"},
                },
            }
            for body in ['{"user": "a"}', '{"user": "b"}', '{"user": "b"}']
        ]
        har = self._har(entries)
        f = tmp_path / "test.har"
        f.write_text(json.dumps(har), encoding="utf-8")

        endpoints = HARParser(str(f)).get_endpoints()
        assert len(endpoints[0].responses) == 2


class TestQueryRouteGeneration:
    """Query-param routes must survive hostile param names and values."""

    def _build(self, query_params):
        responses = [
            {"status": 200, "body": '{"ok": true}'},
            {"status": 200, "body": '{"ok": true, "more": 1}'},
        ]
        request = {"query_params": query_params}
        return build_route(
            "GET", "/api/search", responses, "get_api_search",
            use_smart_fallback=True, sample_request=request,
        )

    def test_default_value_with_quotes_compiles(self):
        route = self._build({"q": 'he said "hi"\\'})
        compile(route, "<route>", "exec")

    def test_hyphenated_param_name_compiles(self):
        route = self._build({"user-id": "42"})
        compile(route, "<route>", "exec")
        assert "user_id: str" in route

    def test_keyword_param_name_compiles(self):
        route = self._build({"class": "premium"})
        compile(route, "<route>", "exec")

    def test_param_starting_with_digit(self):
        route = self._build({"2fa": "on"})
        compile(route, "<route>", "exec")

    def test_normal_params_unchanged(self):
        route = self._build({"category": "electronics", "page": "2"})
        assert "category: str" in route
        assert "page: str" in route
