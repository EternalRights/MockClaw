"""
MockClaw Generation Tests
"""

import ast
import json
from typing import Any

import pytest

from core.parser import HARParser
from core.generator import MockGenerator, GenerationResult
from core.route_builder import build_route, generate_func_name, body_literal
from core.code_extractor import CodeExtractor
from core.generation_strategy import (
    GenerationStrategy,
    LLMGenerationStrategy,
)
from core.prompt_builder import PromptBuilder


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

    def test_missing_field_keeps_its_own_branch(self):
        # A request that omits the discriminating field must still get its own
        # branch (body.get(...) is None), not be silently dropped so its
        # response is unreachable behind the else fallback.
        responses = [
            {"request": {"body": '{"role": "admin"}'}, "status": 200, "body": '{"tier": "admin"}'},
            {"request": {"body": '{}'}, "status": 200, "body": '{"tier": "guest"}'},
        ]
        route = build_route("POST", "/api/access", responses, "post_api_access", use_smart_fallback=True)
        assert 'body.get("role") == "admin"' in route
        assert 'body.get("role") is None' in route
        compile(route, "<route>", "exec")

    def test_null_field_value_is_valid_python(self):
        # JSON null must render as Python None, not the NameError-prone
        # bare `null` that json.dumps would emit.
        responses = [
            {"request": {"body": '{"role": null}'}, "status": 200, "body": '{"tier": "none"}'},
            {"request": {"body": '{"role": "admin"}'}, "status": 200, "body": '{"tier": "admin"}'},
        ]
        route = build_route("POST", "/api/access", responses, "post_api_access", use_smart_fallback=True)
        assert 'body.get("role") == None' in route
        assert 'body.get("role") == "admin"' in route
        compile(route, "<route>", "exec")

    def test_boolean_field_value_is_valid_python(self):
        responses = [
            {"request": {"body": '{"enabled": true}'}, "status": 200, "body": '{"on": 1}'},
            {"request": {"body": '{"enabled": false}'}, "status": 200, "body": '{"off": 1}'},
        ]
        route = build_route("POST", "/api/flag", responses, "post_api_flag", use_smart_fallback=True)
        assert 'body.get("enabled") == True' in route
        assert 'body.get("enabled") == False' in route
        compile(route, "<route>", "exec")


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
        assert result == "None"

    def test_boolean_values_become_python_literals(self):
        result = body_literal('{"active": true, "deleted": false}')
        assert ast.literal_eval(result) == {"active": True, "deleted": False}

    def test_nested_null_and_bool(self):
        result = body_literal('{"meta": null, "items": [1, null, true]}')
        assert ast.literal_eval(result) == {"meta": None, "items": [1, None, True]}


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


class TestPostDataBodyParsing:
    """postData.mimeType carrying parameters must not drop the request body."""

    def _entry(self, mime_type, text='{"msg": "hi"}'):
        return {
            "request": {
                "method": "POST",
                "url": "https://api.example.com/echo",
                "headers": [],
                "queryString": [],
                "postData": {"mimeType": mime_type, "text": text},
            },
            "response": {
                "status": 200,
                "headers": [],
                "content": {"mimeType": "application/json", "text": '{"ok": true}'},
            },
        }

    def _parse(self, mime_type, text, tmp_path):
        har = {"log": {"version": "1.2", "entries": [self._entry(mime_type, text)]}}
        f = tmp_path / "test.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        return HARParser(str(f)).get_endpoints()[0]

    def test_plain_json_mime_type(self, tmp_path):
        ep = self._parse("application/json", '{"msg": "hi"}', tmp_path)
        assert ep.requests[0].body == '{"msg": "hi"}'

    def test_json_with_charset_is_parsed(self, tmp_path):
        ep = self._parse("application/json; charset=utf-8", '{"msg": "hi"}', tmp_path)
        assert ep.requests[0].body == '{"msg": "hi"}'

    def test_non_json_mime_type_ignored(self, tmp_path):
        ep = self._parse("text/plain", "not json", tmp_path)
        assert ep.requests[0].body is None


class TestNullFieldTolerance:
    """HAR exports null out fields the spec marks required; don't blow up."""

    def _parse(self, har, tmp_path):
        f = tmp_path / "test.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        return HARParser(str(f)).get_endpoints()

    def test_null_headers_query_string_and_content(self, tmp_path):
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/users",
                        "headers": None, "queryString": None, "postData": None},
            "response": {"status": 200, "headers": None, "content": None},
        }]}}
        endpoints = self._parse(har, tmp_path)
        assert len(endpoints) == 1
        assert endpoints[0].requests[0].headers == {}
        assert endpoints[0].requests[0].query_params == {}

    def test_null_log_yields_no_endpoints(self, tmp_path):
        assert self._parse({"log": None}, tmp_path) == []

    def test_null_entries_yields_no_endpoints(self, tmp_path):
        assert self._parse({"log": {"entries": None}}, tmp_path) == []


class TestMethodNormalization:
    """HAR methods are not guaranteed upper-case; downstream assumes they are."""

    @staticmethod
    def _entry(method, url, body='{"ok": true}', req_body=None, status=200):
        entry = {
            "request": {
                "method": method, "url": url, "headers": [], "queryString": [],
            },
            "response": {
                "status": status, "headers": [],
                "content": {"mimeType": "application/json", "text": body},
            },
        }
        if req_body is not None:
            entry["request"]["postData"] = {
                "mimeType": "application/json", "text": req_body,
            }
        return entry

    def _parser(self, entries, tmp_path):
        har = {"log": {"version": "1.2", "entries": entries}}
        f = tmp_path / "test.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        return HARParser(str(f))

    def test_lowercase_method_is_upper_cased(self, tmp_path):
        parser = self._parser(
            [self._entry("get", "https://api.example.com/a")], tmp_path,
        )
        assert parser.get_endpoints()[0].method == "GET"

    def test_mixed_case_methods_merge_into_one_endpoint(self, tmp_path):
        # "GET" and "get" used to become two endpoints, so the generated
        # module emitted the same route twice and only one ever served.
        entries = [
            self._entry("GET", "https://api.example.com/dup"),
            self._entry("get", "https://api.example.com/dup", body='{"second": true}'),
        ]
        endpoints = self._parser(entries, tmp_path).get_endpoints()
        assert len(endpoints) == 1
        assert len(endpoints[0].responses) == 2

    def test_missing_method_defaults_to_get(self, tmp_path):
        entry = self._entry("GET", "https://api.example.com/a")
        del entry["request"]["method"]
        assert self._parser([entry], tmp_path).get_endpoints()[0].method == "GET"

    def test_generated_module_has_one_route_per_resource(self, tmp_path):
        entries = [
            self._entry("GET", "https://api.example.com/dup"),
            self._entry("get", "https://api.example.com/dup", body='{"second": true}'),
        ]
        data = self._parser(entries, tmp_path).export_as_dict()
        out_dir = tmp_path / "out"
        MockGenerator(use_smart_fallback=False).generate_all(
            data["endpoints"], output_dir=str(out_dir),
        )
        src = (out_dir / "dynamic_api.py").read_text(encoding="utf-8")
        assert src.count('@app.get("/dup")') == 1

    def test_build_route_enables_smart_routing_for_lowercase(self):
        responses = [
            {"status": 200, "body": '{"r": "a"}', "request": {"body": '{"role": "a"}'}},
            {"status": 200, "body": '{"r": "b"}', "request": {"body": '{"role": "b"}'}},
        ]
        route = build_route(
            "post", "/api/x", responses, "post_api_x", use_smart_fallback=True,
        )
        assert "body.get(" in route
        assert route.startswith('@app.post("/api/x")')

    def test_build_route_keeps_query_routing_for_lowercase_get(self):
        responses = [
            {"status": 200, "body": '{"r": 1}', "request": {"query_params": {"mode": "a"}}},
            {"status": 200, "body": '{"r": 2}', "request": {"query_params": {"mode": "b"}}},
        ]
        route = build_route(
            "get", "/api/q", responses, "get_api_q",
            use_smart_fallback=True, sample_request={"query_params": {"mode": "a"}},
        )
        assert "mode: str" in route
        assert 'if mode == "a"' in route


class TestNonStandardMethodRouting:
    """Verbs FastAPI has no decorator for must still produce a runnable route."""

    def test_standard_verb_uses_shorthand(self):
        route = build_route(
            "GET", "/api/x", [{"status": 200, "body": '{"ok": 1}'}], "get_api_x",
        )
        assert route.startswith('@app.get("/api/x")')

    def test_non_standard_verb_uses_api_route(self):
        # @app.propfind(...) does not exist; the whole generated module used
        # to die with AttributeError on import because of it.
        route = build_route(
            "PROPFIND", "/api/dav", [{"status": 207, "body": '{"dav": 1}'}], "f",
        )
        assert route.startswith('@app.api_route("/api/dav", methods=["PROPFIND"])')

    def test_multi_response_route_uses_api_route(self):
        route = build_route(
            "MKCOL", "/api/col",
            [{"status": 201, "body": '{"a": 1}'}, {"status": 405, "body": '{"e": 1}'}],
            "f",
        )
        assert 'methods=["MKCOL"]' in route

    def test_query_route_uses_api_route(self):
        responses = [
            {"status": 200, "body": '{"r": 1}', "request": {"query_params": {"m": "a"}}},
            {"status": 200, "body": '{"r": 2}', "request": {"query_params": {"m": "b"}}},
        ]
        route = build_route(
            "PROPFIND", "/api/dav", responses, "f",
            use_smart_fallback=True, sample_request={"query_params": {"m": "a"}},
        )
        assert 'methods=["PROPFIND"]' in route

    def test_webdav_route_boots_and_serves(self):
        route = build_route(
            "PROPFIND", "/api/dav", [{"status": 207, "body": '{"dav": 1}'}], "f",
        )
        resp = _serve(route, "PROPFIND", "/api/dav")
        assert resp.status_code == 207, resp.text
        assert resp.json() == {"dav": 1}

    def test_generated_module_with_webdav_method_imports(self, tmp_path):
        entries = [
            TestMethodNormalization._entry("GET", "https://api.example.com/a"),
            TestMethodNormalization._entry(
                "PROPFIND", "https://api.example.com/dav", body='{"dav": 1}',
            ),
        ]
        har = {"log": {"version": "1.2", "entries": entries}}
        f = tmp_path / "test.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()

        out_dir = tmp_path / "out"
        MockGenerator(use_smart_fallback=False).generate_all(
            data["endpoints"], output_dir=str(out_dir),
        )
        src = (out_dir / "dynamic_api.py").read_text(encoding="utf-8")
        assert 'methods=["PROPFIND"]' in src
        compile(src, "dynamic_api.py", "exec")


class TestQueryParamAliasing:
    """A sanitized query name must still answer to the key the HAR recorded."""

    RENAMED = ["user-id", "filter[]", "class", "status", "2fa", "sort by"]

    @staticmethod
    def _route(param, default="a", other="b"):
        responses = [
            {"status": 200, "body": '{"r": "default"}',
             "request": {"query_params": {param: default}}},
            {"status": 200, "body": '{"r": "other"}',
             "request": {"query_params": {param: other}}},
        ]
        return build_route(
            "GET", "/api/s", responses, "f",
            use_smart_fallback=True, sample_request={"query_params": {param: default}},
        )

    def test_renamed_param_is_aliased_to_the_original(self):
        route = self._route("user-id")
        assert 'user_id: str = Query("a", alias="user-id")' in route

    def test_plain_param_gets_no_alias(self):
        route = self._route("mode")
        assert "mode: str" in route
        assert "alias=" not in route

    @pytest.mark.parametrize("param", RENAMED)
    def test_renamed_param_binds_the_recorded_key(self, param):
        # FastAPI binds on the argument name, so without an alias the
        # sanitized name never matched and every request fell through to the
        # default branch -- conditional routing silently never fired.
        route = self._route(param)
        resp = _serve(route, "GET", "/api/s", params={param: "b"})
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"r": "other"}

    def test_default_value_is_still_used(self):
        route = self._route("user-id")
        resp = _serve(route, "GET", "/api/s")
        assert resp.json() == {"r": "default"}

    def test_generated_module_binds_renamed_param(self, tmp_path):
        def entry(value, body):
            return {
                "request": {
                    "method": "GET",
                    "url": f"https://api.example.com/s?user-id={value}",
                    "headers": [],
                    "queryString": [{"name": "user-id", "value": value}],
                },
                "response": {"status": 200, "headers": [],
                             "content": {"mimeType": "application/json",
                                         "text": body}},
                "time": 5,
            }

        f = tmp_path / "test.har"
        f.write_text(json.dumps({"log": {"version": "1.2", "entries": [
            entry("7", '{"r": "seven"}'),
            entry("9", '{"r": "nine"}'),
        ]}}), encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()

        out_dir = tmp_path / "out"
        MockGenerator(use_smart_fallback=True).generate_all(
            data["endpoints"], output_dir=str(out_dir),
        )
        src = (out_dir / "dynamic_api.py").read_text(encoding="utf-8")
        assert 'alias="user-id"' in src

        # The generated module is standalone: exec it and drive the app.
        from fastapi.testclient import TestClient

        namespace: dict[str, Any] = {}
        exec(compile(src, "dynamic_api.py", "exec"), namespace)
        with TestClient(namespace["app"]) as client:
            assert client.get("/s", params={"user-id": "9"}).json() == {"r": "nine"}

    def test_param_named_query_is_suffixed(self):
        # Query is imported by the generated module header, so a parameter
        # using that name would shadow it.
        route = self._route("Query")
        assert "Query_: str" in route
        compile(route, "<route>", "exec")


class TestRecordedStatusReplay:
    """Every recorded success status must reach the client, not just 200."""

    @pytest.mark.parametrize(
        "status_code", [201, 202, 204, 206, 207, 301, 302, 304],
    )
    def test_single_response_replays_status(self, status_code):
        # Returning the bare literal answered 200 for all of these, so a mock
        # of a create or redirect endpoint misreported every response.
        route = build_route(
            "GET", "/api/x", [{"status": status_code, "body": '{"a": 1}'}], "f",
        )
        resp = _serve(route, "GET", "/api/x")
        assert resp.status_code == status_code, resp.text

    def test_plain_200_stays_a_direct_return(self):
        route = build_route(
            "GET", "/api/x", [{"status": 200, "body": '{"a": 1}'}], "f",
        )
        assert "JSONResponse" not in route
        assert "return {" in route

    def test_non_200_is_emitted_via_json_response(self):
        route = build_route(
            "POST", "/api/new", [{"status": 201, "body": '{"id": 7}'}], "f",
        )
        assert 'JSONResponse(status_code=201, content={"id": 7})' in route

    @pytest.mark.parametrize("status_code", [201, 204, 302])
    def test_multi_response_default_replays_status(self, status_code):
        route = build_route(
            "GET", "/api/y",
            [{"status": status_code, "body": '{"a": 1}'},
             {"status": 500, "body": '{"e": 1}'}],
            "f",
        )
        resp = _serve(route, "GET", "/api/y")
        assert resp.status_code == status_code, resp.text

    def test_smart_route_branch_replays_status(self):
        responses = [
            {"status": 201, "body": '{"created": true}',
             "request": {"body": '{"role": "a"}'}},
            {"status": 200, "body": '{"ok": true}',
             "request": {"body": '{"role": "b"}'}},
        ]
        route = build_route(
            "POST", "/api/z", responses, "f", use_smart_fallback=True,
        )
        resp = _serve(route, "POST", "/api/z", json={"role": "a"})
        assert resp.status_code == 201, resp.text
        assert resp.json() == {"created": True}

    def test_query_route_branch_replays_status(self):
        responses = [
            {"status": 202, "body": '{"r": 1}',
             "request": {"query_params": {"m": "a"}}},
            {"status": 200, "body": '{"r": 2}',
             "request": {"query_params": {"m": "b"}}},
        ]
        route = build_route(
            "GET", "/api/q", responses, "f",
            use_smart_fallback=True, sample_request={"query_params": {"m": "a"}},
        )
        resp = _serve(route, "GET", "/api/q", params={"m": "a"})
        assert resp.status_code == 202, resp.text

    @pytest.mark.parametrize("status_code", [400, 404, 418, 500, 503])
    def test_error_statuses_are_replayed(self, status_code):
        route = build_route(
            "GET", "/api/err", [{"status": status_code, "body": '{"e": 1}'}], "f",
        )
        assert f"JSONResponse(status_code={status_code}" in route
        resp = _serve(route, "GET", "/api/err")
        assert resp.status_code == status_code, resp.text
        # The recorded body must come back as captured, not wrapped in detail.
        assert resp.json() == {"e": 1}

    def test_smart_route_error_body_is_replayed_verbatim(self):
        responses = [
            {"status": 403, "body": '{"err": "nope"}',
             "request": {"body": '{"role": "guest"}'}},
            {"status": 200, "body": '{"ok": true}',
             "request": {"body": '{"role": "admin"}'}},
        ]
        route = build_route(
            "POST", "/api/p", responses, "f", use_smart_fallback=True,
        )
        resp = _serve(route, "POST", "/api/p", json={"role": "guest"})
        assert resp.status_code == 403, resp.text
        assert resp.json() == {"err": "nope"}

    def test_query_route_error_body_is_replayed_verbatim(self):
        responses = [
            {"status": 418, "body": '{"e": "teapot"}',
             "request": {"query_params": {"m": "a"}}},
            {"status": 200, "body": '{"ok": true}',
             "request": {"query_params": {"m": "b"}}},
        ]
        route = build_route(
            "GET", "/api/q", responses, "f",
            use_smart_fallback=True, sample_request={"query_params": {"m": "a"}},
        )
        resp = _serve(route, "GET", "/api/q", params={"m": "a"})
        assert resp.status_code == 418, resp.text
        assert resp.json() == {"e": "teapot"}

    def test_text_error_body_is_replayed_verbatim(self):
        route = build_route(
            "GET", "/api/t", [{"status": 500, "body": "internal boom"}], "f",
        )
        resp = _serve(route, "GET", "/api/t")
        assert resp.status_code == 500, resp.text
        assert resp.json() == "internal boom"

    def test_generated_module_replays_status_end_to_end(self, tmp_path):
        entries = [
            TestMethodNormalization._entry(
                "GET", "https://api.example.com/made", status=201,
                body='{"id": 7}',
            ),
        ]
        har = {"log": {"version": "1.2", "entries": entries}}
        f = tmp_path / "test.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()

        out_dir = tmp_path / "out"
        MockGenerator(use_smart_fallback=False).generate_all(
            data["endpoints"], output_dir=str(out_dir),
        )
        src = (out_dir / "dynamic_api.py").read_text(encoding="utf-8")
        assert "status_code=201" in src

        # The generated module is standalone: exec it as-is and drive the app.
        from fastapi.testclient import TestClient

        namespace: dict[str, Any] = {}
        exec(compile(src, "dynamic_api.py", "exec"), namespace)
        with TestClient(namespace["app"]) as client:
            resp = client.get("/made")
            assert resp.status_code == 201, resp.text
            assert resp.json() == {"id": 7}


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

    def test_conditional_routing_by_query_param(self):
        responses = [
            {"status": 200, "body": '{"result": "success"}', "request": {"query_params": {"mode": "success"}}},
            {"status": 500, "body": '{"error": "boom"}', "request": {"query_params": {"mode": "error"}}},
        ]
        request = {"query_params": {"mode": "success"}}
        route = build_route(
            "GET", "/api/search", responses, "get_api_search",
            use_smart_fallback=True, sample_request=request,
        )
        assert 'if mode == "success"' in route
        assert 'elif mode == "error"' in route
        compile(route, "<route>", "exec")

    def test_conditional_routing_joins_multiple_params(self):
        responses = [
            {"status": 200, "body": '{"tier": "us"}', "request": {"query_params": {"role": "admin", "region": "us"}}},
            {"status": 200, "body": '{"tier": "eu"}', "request": {"query_params": {"role": "admin", "region": "eu"}}},
            {"status": 200, "body": '{"tier": "basic"}', "request": {"query_params": {"role": "user", "region": "us"}}},
        ]
        request = {"query_params": {"role": "admin", "region": "us"}}
        route = build_route(
            "GET", "/api/perm", responses, "get_api_perm",
            use_smart_fallback=True, sample_request=request,
        )
        assert " and " in route
        compile(route, "<route>", "exec")

    def test_reserved_import_name_is_suffixed(self):
        # A query param named "status" would shadow the module-level status
        # import; it must be emitted as status_ instead, and the branch on it
        # has to keep working.
        responses = [
            {"status": 200, "body": '{"ok": true}', "request": {"query_params": {"status": "ok"}}},
            {"status": 500, "body": '{"err": 1}', "request": {"query_params": {"status": "bad"}}},
        ]
        request = {"query_params": {"status": "ok"}}
        route = build_route(
            "GET", "/api/healthz", responses, "get_api_healthz",
            use_smart_fallback=True, sample_request=request,
        )
        assert "status_: str" in route
        assert "status_code=500" in route
        compile(route, "<route>", "exec")


def _exec_route(route: str):
    """Exec a generated route into a throwaway FastAPI app.

    Compiling a route only proves it parses; importing it and reading the
    function back is what catches undefined names and invented constants.
    The namespace mirrors the header the generator writes into the mock
    module, so a route that leans on JSONResponse is exercised the same way.
    """
    from fastapi import FastAPI, HTTPException, Query, Request, Response, status
    from fastapi.responses import JSONResponse

    app = FastAPI()
    namespace: dict[str, Any] = {
        "app": app,
        "HTTPException": HTTPException,
        "Request": Request,
        "Response": Response,
        "JSONResponse": JSONResponse,
        "Query": Query,
        "status": status,
        "Any": Any,
    }
    exec(compile(route, "<route>", "exec"), namespace)
    return app, namespace


def _serve(route: str, method: str, path: str, **kwargs):
    """Exec a generated route and issue one request through TestClient."""
    from fastapi.testclient import TestClient

    app, _ = _exec_route(route)
    with TestClient(app, raise_server_exceptions=False) as client:
        return client.request(method, path, **kwargs)


class TestStatusCodeRendering:
    """A recorded status must survive into the generated response, unchanged."""

    def test_unmapped_status_is_not_silently_remapped(self):
        # 418 used to fall through to HTTP_500_INTERNAL_SERVER_ERROR, so the
        # mock answered 500 for a recorded 418.
        route = build_route(
            "POST", "/api/teapot", [{"status": 418, "body": '{"e": 1}'}],
            "post_api_teapot",
        )
        assert "status_code=418" in route
        assert "HTTP_500" not in route

    def test_unmapped_status_does_not_invent_a_constant(self):
        # A single-response query route used to emit status.HTTP_418_ERROR,
        # an attribute fastapi.status does not have.
        responses = [
            {"status": 418, "body": '{"e": 1}', "request": {"query_params": {"q": "1"}}},
            {"status": 200, "body": '{"ok": 1}'},
        ]
        route = build_route(
            "GET", "/api/teapot", responses, "get_api_teapot",
            use_smart_fallback=True, sample_request={"query_params": {"q": "1"}},
        )
        assert "HTTP_418_ERROR" not in route
        assert "status_code=418" in route

    def test_status_is_emitted_as_a_plain_integer(self):
        # Statuses are no longer spelled as status.HTTP_* constants: a plain
        # integer works for every code, including ones with no named constant.
        route = build_route(
            "GET", "/api/thing", [{"status": 404, "body": '{"e": 1}'}],
            "get_api_thing",
        )
        assert "status_code=404" in route
        assert "HTTP_404" not in route

    def test_smart_route_unmapped_status_uses_int_literal(self):
        responses = [
            {"status": 200, "body": '{"p": "a"}', "request": {"body": '{"role": "a"}'}},
            {"status": 418, "body": '{"p": "b"}', "request": {"body": '{"role": "b"}'}},
            {"status": 418, "body": '{"p": "c"}', "request": {"body": '{"role": "c"}'}},
        ]
        route = build_route(
            "POST", "/api/x", responses, "post_api_x", use_smart_fallback=True,
        )
        assert "status.HTTP_418" not in route
        assert "status_code=418" in route


class TestGeneratedRouteRuntime:
    """Generated routes must run, not merely compile."""

    def test_unmapped_status_is_served_verbatim(self):
        route = build_route(
            "POST", "/api/teapot", [{"status": 418, "body": '{"e": "teapot"}'}],
            "post_api_teapot",
        )
        resp = _serve(route, "POST", "/api/teapot")
        assert resp.status_code == 418, resp.text

    def test_query_route_unmapped_status_is_served_verbatim(self):
        responses = [
            {"status": 418, "body": '{"e": 1}', "request": {"query_params": {"q": "1"}}},
            {"status": 200, "body": '{"ok": 1}'},
        ]
        route = build_route(
            "GET", "/api/teapot", responses, "get_api_teapot",
            use_smart_fallback=True, sample_request={"query_params": {"q": "1"}},
        )
        resp = _serve(route, "GET", "/api/teapot")
        assert resp.status_code == 418, resp.text

    def test_branch_on_unsampled_query_param_runs(self):
        # "sort" only appears in the second response, so the branch tested a
        # name that was never a function argument -> NameError at runtime.
        responses = [
            {"status": 200, "body": '{"tier": "a"}',
             "request": {"query_params": {"page": "1"}}},
            {"status": 200, "body": '{"tier": "b"}',
             "request": {"query_params": {"page": "1", "sort": "desc"}}},
        ]
        route = build_route(
            "GET", "/api/list", responses, "get_api_list",
            use_smart_fallback=True, sample_request={"query_params": {"page": "1"}},
        )
        resp = _serve(route, "GET", "/api/list", params={"page": "1", "sort": "desc"})
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"tier": "b"}

    def test_smart_route_condition_matches_second_branch(self):
        responses = [
            {"status": 200, "body": '{"ok": true}', "request": {"body": '{"role": "admin"}'}},
            {"status": 403, "body": '{"err": "nope"}', "request": {"body": '{"role": "guest"}'}},
        ]
        route = build_route(
            "POST", "/api/perm", responses, "post_api_perm", use_smart_fallback=True,
        )
        allowed = _serve(route, "POST", "/api/perm", json={"role": "admin"})
        assert allowed.status_code == 200, allowed.text
        denied = _serve(route, "POST", "/api/perm", json={"role": "guest"})
        assert denied.status_code == 403, denied.text
        assert denied.json() == {"err": "nope"}


class TestScenarioListingEscaping:
    """Raw bodies in the scenario listing must not break the generated file."""

    _TRIPLE_QUOTE_BODY = '{"note": """raw triple quote""" }'

    def _multi_response_route(self, body):
        responses = [
            {"status": 200, "body": body},
            {"status": 200, "body": '{"other": 1}'},
        ]
        return build_route("GET", "/api/quoted", responses, "get_api_quoted")

    def test_triple_quote_body_still_compiles(self):
        # An unescaped """ terminated the docstring early, so the whole
        # generated module raised SyntaxError and the mock never started.
        route = self._multi_response_route(self._TRIPLE_QUOTE_BODY)
        compile(route, "<route>", "exec")

    def test_triple_quote_body_route_boots(self):
        route = self._multi_response_route(self._TRIPLE_QUOTE_BODY)
        resp = _serve(route, "GET", "/api/quoted")
        assert resp.status_code == 200, resp.text

    def test_query_route_listing_is_escaped(self):
        responses = [
            {"status": 200, "body": self._TRIPLE_QUOTE_BODY,
             "request": {"query_params": {"q": "1"}}},
            {"status": 200, "body": '{"other": 1}',
             "request": {"query_params": {"q": "2"}}},
        ]
        route = build_route(
            "GET", "/api/quoted", responses, "get_api_quoted",
            use_smart_fallback=True, sample_request={"query_params": {"q": "1"}},
        )
        compile(route, "<route>", "exec")
        assert '"""raw triple quote"""' not in route

    def test_listing_still_shows_the_raw_body(self):
        # Escaping must not corrupt what the listing *displays*.
        route = self._multi_response_route(self._TRIPLE_QUOTE_BODY)
        _, namespace = _exec_route(route)
        assert self._TRIPLE_QUOTE_BODY in namespace["get_api_quoted"].__doc__

    def test_backslash_body_is_displayed_verbatim(self):
        body = '{"path": "C:\\\\Users\\\\x"}'
        route = self._multi_response_route(body)
        _, namespace = _exec_route(route)
        assert body in namespace["get_api_quoted"].__doc__


class TestLLMCodeValidation:
    """LLM output that fails to compile must never reach the mock file."""

    def test_valid_python(self):
        assert LLMGenerationStrategy._is_valid_python(
            "@app.get('/x')\nasync def x():\n    return {}\n"
        )

    def test_syntax_error(self):
        assert not LLMGenerationStrategy._is_valid_python("def broken(:\n")

    def test_empty_string(self):
        assert not LLMGenerationStrategy._is_valid_python("")

    def test_falls_back_on_broken_code(self):
        class _FakeResponse:
            def __init__(self, content):
                self.choices = [type(
                    "C", (),
                    {"message": type("M", (), {"content": content})()},
                )()]

        class _FakeClient:
            def __init__(self, content):
                self.chat = type(
                    "Chat", (),
                    {"completions": type(
                        "Comp", (),
                        {"create": lambda self, **kw: _FakeResponse(content)},
                    )()},
                )()

        class _FakeManager:
            def __init__(self, content):
                self._content = content

            def get_client(self):
                return _FakeClient(self._content)

            def call_with_retry(self, fn, *args, **kwargs):
                return fn(*args, **kwargs)

        class _StubFallback(GenerationStrategy):
            def generate(self, endpoint_data):
                return "@app.get('/stub')\nasync def stub():\n    return {}\n"

        strategy = LLMGenerationStrategy(
            client_manager=_FakeManager("def broken(:\n"),
            prompt_builder=PromptBuilder(),
            code_extractor=CodeExtractor(),
            fallback=_StubFallback(),
        )
        code = strategy.generate({
            "method": "GET",
            "resource_path": "/x",
            "sample_request": {},
            "sample_responses": [],
        })
        assert "stub" in code

    def test_raises_without_fallback_on_broken_code(self):
        class _FakeResponse:
            def __init__(self, content):
                self.choices = [type(
                    "C", (),
                    {"message": type("M", (), {"content": content})()},
                )()]

        class _FakeClient:
            def __init__(self, content):
                self.chat = type(
                    "Chat", (),
                    {"completions": type(
                        "Comp", (),
                        {"create": lambda self, **kw: _FakeResponse(content)},
                    )()},
                )()

        class _FakeManager:
            def __init__(self, content):
                self._content = content

            def get_client(self):
                return _FakeClient(self._content)

            def call_with_retry(self, fn, *args, **kwargs):
                return fn(*args, **kwargs)

        strategy = LLMGenerationStrategy(
            client_manager=_FakeManager("def broken(:\n"),
            prompt_builder=PromptBuilder(),
            code_extractor=CodeExtractor(),
        )
        with pytest.raises(RuntimeError):
            strategy.generate({
                "method": "GET",
                "resource_path": "/x",
                "sample_request": {},
                "sample_responses": [],
            })
