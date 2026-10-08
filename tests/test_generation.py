"""
MockClaw Generation Tests
"""

import ast
import json
from typing import Any

import pytest

from core.parser import HARParser
from core.generator import MockGenerator, GenerationResult, _get_mock_server_header
from core.route_builder import build_route, generate_func_name, body_literal, _arg_signature
from core.code_extractor import CodeExtractor
from core.generation_strategy import (
    GenerationStrategy,
    LLMGenerationStrategy,
    TemplateGenerationStrategy,
)
from core.prompt_builder import PromptBuilder, _MAX_BODY_CHARS


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


class TestUrlPathDecoding:
    """Recorded URLs are percent-encoded; routes match the decoded path.

    A HAR stores the URL as it went on the wire, and browsers always encode a
    non-ASCII path. Emitting the encoded form produced a decorator no request
    could ever reach -- Starlette matches against the path the server has
    already decoded -- so a capture of /api/%E7%94%A8%E6%88%B7/1 mocked 404
    for the very request it recorded.
    """

    def _path(self, url):
        return HARParser("unused.har")._extract_url_path(url)

    @pytest.mark.parametrize("url, expected", [
        ("https://api.example.com/api/%E7%94%A8%E6%88%B7/1", "/api/用户/{id}"),
        ("https://api.example.com/api/my%20file", "/api/my file"),
        ("https://api.example.com/api/a%2Fb", "/api/a/b"),
        ("https://api.example.com/api/%E4%B8%AD", "/api/中"),
    ])
    def test_encoded_segments_are_decoded(self, url, expected):
        assert self._path(url) == expected

    def test_plus_is_not_a_space(self):
        # unquote_plus would turn the literal '+' into a space and move the
        # route to a path the client never asks for.
        assert self._path("https://api.example.com/api/a+b") == "/api/a+b"

    def test_lone_percent_is_left_alone(self):
        # Not a valid escape sequence; unquote must not mangle it.
        assert self._path("https://api.example.com/api/100%discount") == "/api/100%discount"

    def test_double_encoded_is_decoded_once(self):
        # %2520 is an encoded "%20"; one pass yields "%20", which is exactly
        # what the server hands over for that request.
        assert self._path("https://api.example.com/api/%2520") == "/api/%20"

    def test_already_decoded_path_is_unchanged(self):
        assert self._path("https://api.example.com/api/用户/1") == "/api/用户/{id}"

    def test_plain_path_is_unchanged(self):
        assert self._path("https://api.example.com/v1/users") == "/v1/users"

    def test_query_is_stripped_before_decoding(self):
        # Only the path is decoded: a '+' or '%' in the query string must not
        # bleed into the resource path.
        assert self._path("https://api.example.com/api/x?q=a+b%2Fc") == "/api/x"

    def test_recorded_url_keeps_its_encoded_form(self, tmp_path):
        # The raw recording stays traceable; only the derived path is decoded.
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET",
                        "url": "https://api.example.com/api/%E7%94%A8%E6%88%B7/1",
                        "headers": [], "queryString": []},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json", "text": '{"ok": 1}'}},
            "time": 10,
        }]}}
        f = tmp_path / "t.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()
        assert data["endpoints"][0]["resource_path"] == "/api/用户/{id}"
        assert data["endpoints"][0]["sample_request"]["url"].endswith("%E7%94%A8%E6%88%B7/1")

    def test_encoded_path_generates_a_reachable_route(self, tmp_path):
        # End-to-end: the route must answer the request the HAR recorded.
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET",
                        "url": "https://api.example.com/api/%E7%94%A8%E6%88%B7/1",
                        "headers": [], "queryString": []},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json",
                                     "text": '{"name": "用户一"}'}},
            "time": 10,
        }]}}
        f = tmp_path / "t.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()
        route = MockGenerator(use_smart_fallback=False).generate_endpoint(
            data["endpoints"][0]
        ).generated_code
        assert '@app.get("/api/用户/{id}")' in route

        resp = _serve(route, "GET", "/api/用户/1")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"name": "用户一"}


class TestRepeatedPathPlaceholders:
    """Two dynamic segments must not reuse one placeholder name.

    Starlette rejects the path outright ("Duplicated param name id") and the
    handler would declare the same argument twice, so the ordinary nested
    resource shape /users/1/orders/2 produced a mock file that could not be
    imported at all -- every endpoint in it went down.
    """

    def _path(self, url):
        return HARParser("unused.har")._extract_url_path(url)

    def test_two_numbered_segments_get_distinct_names(self):
        assert self._path(
            "https://api.example.com/users/1/orders/2"
        ) == "/users/{id}/orders/{id_2}"

    def test_three_numbered_segments_get_distinct_names(self):
        assert self._path(
            "https://api.example.com/a/1/b/2/c/3"
        ) == "/a/{id}/b/{id_2}/c/{id_3}"

    def test_two_uuids_get_distinct_names(self):
        first = "550e8400-e29b-41d4-a716-446655440000"
        second = "550e8400-e29b-41d4-a716-446655440001"
        assert self._path(
            f"https://api.example.com/a/{first}/b/{second}"
        ) == "/a/{uuid}/b/{uuid_2}"

    def test_uuid_and_numbered_segments_do_not_collide(self):
        uuid = "550e8400-e29b-41d4-a716-446655440000"
        assert self._path(
            f"https://api.example.com/a/{uuid}/b/7"
        ) == "/a/{uuid}/b/{id}"

    def test_single_segment_keeps_the_plain_name(self):
        assert self._path("https://api.example.com/users/1") == "/users/{id}"

    def test_nested_id_route_imports_and_serves(self, tmp_path):
        # End-to-end: the generated module used to raise SyntaxError on import.
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET",
                        "url": "https://api.example.com/users/1/orders/2",
                        "headers": [], "queryString": []},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json",
                                     "text": '{"order": 2}'}},
            "time": 10,
        }]}}
        f = tmp_path / "t.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()
        route = MockGenerator(use_smart_fallback=False).generate_endpoint(
            data["endpoints"][0]
        ).generated_code
        assert '@app.get("/users/{id}/orders/{id_2}")' in route
        assert "async def get_users_id_orders_id_2(id: str, id_2: str):" in route

        resp = _serve(route, "GET", "/users/7/orders/9")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"order": 2}


class TestUniqueArgumentNames:
    """A recorded key must never collide with another handler argument.

    Python rejects a duplicate argument outright, so one colliding query key
    ("/users/{id}?id=7", "?a b=1&a-b=2") took the whole mock file down.
    """

    def test_query_key_matching_a_path_placeholder(self):
        assert _arg_signature("/users/{id}", {"id": "7"}) == [
            "id: str",
            'id_2: str = Query("7", alias="id")',
        ]

    def test_query_keys_that_sanitize_alike(self):
        assert _arg_signature("/s", {"a b": "1", "a-b": "2"}) == [
            'a_b: str = Query("1", alias="a b")',
            'a_b_2: str = Query("2", alias="a-b")',
        ]

    def test_reserved_key_suffix_collision(self):
        # "class" becomes "class_", which would collide with the recorded
        # "class_" key.
        assert _arg_signature("/s", {"class": "1", "class_": "2"}) == [
            'class_: str = Query("1", alias="class")',
            'class__2: str = Query("2", alias="class_")',
        ]

    def test_plain_path_args_lead_the_defaulted_ones(self):
        # A renamed placeholder carries a default, and Python forbids a
        # defaulted parameter ahead of a required one.
        assert _arg_signature("/a/{class}/b/{id}", None) == [
            "id: str",
            'class_: str = Path(..., alias="class")',
        ]

    def test_route_with_colliding_query_key_imports_and_serves(self):
        route = build_route(
            "GET", "/users/{id}", [{"status": 200, "body": '{"ok": 1}'}],
            "get_users_id", sample_request={"query_params": {"id": "7"}},
        )
        resp = _serve(route, "GET", "/users/7", params={"id": "7"})
        assert resp.status_code == 200, resp.text

    def test_both_aliased_query_keys_are_discoverable(self):
        # openapi shows FastAPI bound each alias to its own recorded key.
        route = build_route(
            "GET", "/s", [{"status": 200, "body": '{"ok": 1}'}],
            "get_s", sample_request={"query_params": {"a b": "1", "a-b": "2"}},
        )
        app, _ = _exec_route(route)
        params = app.openapi()["paths"]["/s"]["get"].get("parameters", [])
        assert {(p["name"], p["in"]) for p in params} == {("a b", "query"), ("a-b", "query")}


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

    def test_null_time_does_not_crash_the_parse(self, tmp_path):
        # int(None) used to raise TypeError inside _parse_response, taking the
        # whole file down rather than skipping the timing.
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/a",
                        "headers": [], "queryString": []},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json",
                                     "text": '{"ok": true}'}},
            "time": None,
        }]}}
        endpoints = self._parse(har, tmp_path)
        assert len(endpoints) == 1
        assert endpoints[0].responses[0].latency_ms == 0

    def test_null_status_falls_back_to_200(self, tmp_path):
        # A null status used to reach the generated route verbatim and emit
        # JSONResponse(status_code=None, ...).
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/a",
                        "headers": [], "queryString": []},
            "response": {"status": None, "headers": [],
                         "content": {"mimeType": "application/json",
                                     "text": '{"ok": true}'}},
            "time": 50,
        }]}}
        endpoints = self._parse(har, tmp_path)
        assert endpoints[0].responses[0].status == 200

    def test_null_status_never_reaches_generated_code(self, tmp_path):
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/a",
                        "headers": [], "queryString": []},
            "response": {"status": None, "headers": [],
                         "content": {"mimeType": "application/json",
                                     "text": '{"ok": true}'}},
            "time": 50,
        }]}}
        f = tmp_path / "test.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()

        out_dir = tmp_path / "out"
        MockGenerator(use_smart_fallback=False).generate_all(
            data["endpoints"], output_dir=str(out_dir),
        )
        src = (out_dir / "dynamic_api.py").read_text(encoding="utf-8")
        assert "status_code=None" not in src
        assert "None" not in src.split("# === Generated Endpoints ===")[-1]

    def test_null_response_fields_still_parse(self, tmp_path):
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/a",
                        "headers": [], "queryString": []},
            "response": None,
            "time": None,
        }]}}
        endpoints = self._parse(har, tmp_path)
        assert len(endpoints) == 1
        assert endpoints[0].responses[0].status == 200
        assert endpoints[0].responses[0].latency_ms == 0

    def test_null_query_value_becomes_empty_string(self, tmp_path):
        # Chrome writes "value": null for query params it could not resolve.
        # get('value', '') only defaults on a *missing* key, so a Python None
        # used to travel on and become the default `q: str = "None"` plus an
        # unreachable `if q == None` branch in the generated handler.
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/s",
                        "headers": [], "queryString": [{"name": "q", "value": None}]},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json", "text": "{}"}},
            "time": 10,
        }]}}
        endpoints = self._parse(har, tmp_path)
        assert endpoints[0].requests[0].query_params == {"q": ""}

    def test_null_header_value_becomes_empty_string(self, tmp_path):
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/a",
                        "headers": [{"name": "X-Token", "value": None}],
                        "queryString": []},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json", "text": "{}"}},
            "time": 10,
        }]}}
        endpoints = self._parse(har, tmp_path)
        assert endpoints[0].requests[0].headers == {"x-token": ""}

    def test_null_url_does_not_crash_the_parse(self, tmp_path):
        # urlparse(None) raised inside the static-asset check before the
        # request was even parsed, taking the whole file down. The entry has
        # no url at all now, so it is dropped rather than turned into a
        # fabricated "GET /" that could merge into a real root entry.
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": None, "headers": [], "queryString": []},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json", "text": "{}"}},
            "time": 10,
        }]}}
        assert self._parse(har, tmp_path) == []

    def test_non_string_url_does_not_crash_the_parse(self, tmp_path):
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": 123, "headers": [], "queryString": []},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json", "text": "{}"}},
            "time": 10,
        }]}}
        endpoints = self._parse(har, tmp_path)
        assert len(endpoints) == 1
        assert endpoints[0].resource_path == "/{id}"

    def test_non_mapping_list_items_are_skipped(self, tmp_path):
        # A bare string where the HAR spec says object used to raise
        # AttributeError ('str' object has no attribute 'get').
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/a",
                        "headers": ["not-an-object"],
                        "queryString": ["not-an-object"]},
            "response": {"status": 200, "headers": ["not-an-object"],
                         "content": {"mimeType": "application/json", "text": "{}"}},
            "time": 10,
        }]}}
        endpoints = self._parse(har, tmp_path)
        assert len(endpoints) == 1
        assert endpoints[0].requests[0].headers == {}
        assert endpoints[0].requests[0].query_params == {}

    def test_non_mapping_containers_do_not_crash(self, tmp_path):
        har = {"log": {"version": "1.2", "entries": [{
            "request": "oops",
            "response": "oops",
            "time": 10,
        }]}}
        # Both are strings where objects belong, so the entry carries no url
        # and no path to mock. It is dropped instead of becoming a "GET /".
        assert self._parse(har, tmp_path) == []

    def test_null_entry_is_dropped_not_fabricated(self, tmp_path):
        # A null in the entries array is not an entry; coercing it to {} would
        # fabricate a bogus "GET /" endpoint next to the real one.
        har = {"log": {"version": "1.2", "entries": [None, {
            "request": {"method": "GET", "url": "https://api.example.com/real",
                        "headers": [], "queryString": []},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json", "text": "{}"}},
            "time": 10,
        }]}}
        endpoints = self._parse(har, tmp_path)
        assert len(endpoints) == 1
        assert endpoints[0].resource_path == "/real"


class TestNullQueryValueRouting:
    """A null query value must replay as an absent param, not as "None"."""

    def _route_from(self, har, tmp_path, smart=True):
        f = tmp_path / "q.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()
        return MockGenerator(use_smart_fallback=smart).generate_endpoint(
            data["endpoints"][0]
        ).generated_code

    _HAR = {"log": {"version": "1.2", "entries": [
        {"request": {"method": "GET", "url": "https://api.example.com/search",
                     "headers": [], "queryString": [{"name": "q", "value": None}]},
         "response": {"status": 404, "headers": [],
                      "content": {"mimeType": "application/json",
                                  "text": '{"err": "missing q"}'}},
         "time": 10},
        {"request": {"method": "GET", "url": "https://api.example.com/search?q=world",
                     "headers": [], "queryString": [{"name": "q", "value": "world"}]},
         "response": {"status": 200, "headers": [],
                      "content": {"mimeType": "application/json",
                                  "text": '{"r": "world"}'}},
         "time": 10},
    ]}}

    def test_recorded_scenarios_both_replay(self, tmp_path):
        # The mock used to answer 200 for the no-q request: the null value
        # became the string "None" and `q == None` was unreachable, so the
        # recorded 404 scenario was silently swallowed.
        route = self._route_from(self._HAR, tmp_path)
        assert "None" not in route

        missing = _serve(route, "GET", "/search")
        assert missing.status_code == 404, missing.text
        assert missing.json() == {"err": "missing q"}

        present = _serve(route, "GET", "/search", params={"q": "world"})
        assert present.status_code == 200, present.text
        assert present.json() == {"r": "world"}

    def test_default_mode_uses_empty_string_default(self, tmp_path):
        route = self._route_from(self._HAR, tmp_path, smart=False)
        assert 'q: str = ""' in route
        assert '"None"' not in route


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

    def test_default_branch_uses_the_first_2xx_response(self):
        # The fallback picks the first 2xx response, not simply the first one.
        # Watch the parentheses: `200 <= x or 200 < 300` is always true, which
        # silently turned this into "always take all_responses[0]".
        responses = [
            {"status": 500, "body": '{"e": "boom"}',
             "request": {"body": '{"role": "x"}'}},
            {"status": 200, "body": '{"ok": true}',
             "request": {"body": '{"role": "y"}'}},
        ]
        route = build_route(
            "POST", "/api/p", responses, "f", use_smart_fallback=True,
        )
        resp = _serve(route, "POST", "/api/p", json={"role": "zzz"})
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"ok": True}

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


class TestQueryStringFromUrl:
    """The URL carries the query on its own; queryString may be absent.

    Browsers fill queryString in, but hand-written and some non-browser HARs
    leave it empty -- and reading only that field produced a mock with no
    query parameters at all, so every variant of the URL was answered with
    the first recorded response.
    """

    def _entry(self, url, body, query_string=None):
        return {
            "request": {"method": "GET", "url": url, "headers": [],
                        "queryString": query_string or []},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json", "text": body}},
            "time": 10,
        }

    def _endpoint(self, tmp_path, entries):
        f = tmp_path / "t.har"
        f.write_text(json.dumps({"log": {"version": "1.2", "entries": entries}}),
                     encoding="utf-8")
        return HARParser(str(f)).export_as_dict()["endpoints"][0]

    def test_query_only_in_the_url_is_picked_up(self, tmp_path):
        endpoint = self._endpoint(tmp_path, [
            self._entry("https://api.example.com/products?category=books", '{"c": 1}'),
        ])
        assert endpoint["sample_request"]["query_params"] == {"category": "books"}

    def test_two_url_variants_route_to_their_own_response(self, tmp_path):
        endpoint = self._endpoint(tmp_path, [
            self._entry("https://api.example.com/products?category=electronics", '{"c": "e"}'),
            self._entry("https://api.example.com/products?category=books", '{"c": "b"}'),
        ])
        route = MockGenerator(use_smart_fallback=True).generate_endpoint(endpoint).generated_code

        assert _serve(route, "GET", "/products", params={"category": "electronics"}).json() == {"c": "e"}
        assert _serve(route, "GET", "/products", params={"category": "books"}).json() == {"c": "b"}

    def test_query_string_wins_when_both_describe_the_same_key(self, tmp_path):
        endpoint = self._endpoint(tmp_path, [
            self._entry("https://api.example.com/s?status=from-url", '{"s": 1}',
                        query_string=[{"name": "status", "value": "from-field"}]),
        ])
        assert endpoint["sample_request"]["query_params"] == {"status": "from-field"}

    def test_url_parameters_missing_from_query_string_are_added(self, tmp_path):
        endpoint = self._endpoint(tmp_path, [
            self._entry("https://api.example.com/s?a=1&b=2", '{"s": 1}',
                        query_string=[{"name": "a", "value": "1"}]),
        ])
        assert endpoint["sample_request"]["query_params"] == {"a": "1", "b": "2"}

    def test_encoded_query_values_arrive_decoded(self, tmp_path):
        # The route compares against what the server hands over, and Starlette
        # decodes a query value before the handler sees it.
        endpoint = self._endpoint(tmp_path, [
            self._entry("https://api.example.com/s?q=%E4%B8%AD", '{"s": 1}'),
        ])
        assert endpoint["sample_request"]["query_params"] == {"q": "中"}

    def test_a_blank_value_is_kept(self, tmp_path):
        endpoint = self._endpoint(tmp_path, [
            self._entry("https://api.example.com/s?flag=", '{"s": 1}'),
        ])
        assert endpoint["sample_request"]["query_params"] == {"flag": ""}

    def test_no_query_leaves_the_parameters_empty(self, tmp_path):
        endpoint = self._endpoint(tmp_path, [
            self._entry("https://api.example.com/plain", '{"s": 1}'),
        ])
        assert endpoint["sample_request"]["query_params"] == {}


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
    from fastapi import FastAPI, HTTPException, Path, Query, Request, Response, status
    from fastapi.responses import JSONResponse

    app = FastAPI()
    namespace: dict[str, Any] = {
        "app": app,
        "HTTPException": HTTPException,
        "Request": Request,
        "Response": Response,
        "JSONResponse": JSONResponse,
        "Query": Query,
        "Path": Path,
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


class TestNonJsonResponseReplay:
    """A non-JSON recorded response must replay verbatim, not JSON-quoted.

    Returning the recorded text as a Python string made FastAPI JSON-encode
    it -- a recorded ``plain text`` went out as ``"plain text"`` -- and forced
    the content-type to application/json, so a client parsing the recorded
    type could no longer read the response at all.
    """

    def test_text_plain_body_is_not_json_quoted(self):
        route = build_route(
            "GET", "/api/plain",
            [{"status": 200, "body": "plain text", "content_type": "text/plain"}],
            "get_api_plain",
        )
        assert 'Response(content="plain text", media_type="text/plain")' in route

        resp = _serve(route, "GET", "/api/plain")
        assert resp.status_code == 200
        assert resp.text == "plain text", resp.text
        assert resp.headers["content-type"].startswith("text/plain")

    def test_recorded_charset_is_preserved(self):
        route = build_route(
            "GET", "/api/plain",
            [{"status": 200, "body": "hi", "content_type": "text/plain; charset=utf-8"}],
            "get_api_plain",
        )
        assert 'media_type="text/plain; charset=utf-8"' in route
        resp = _serve(route, "GET", "/api/plain")
        assert resp.headers["content-type"] == "text/plain; charset=utf-8"

    def test_non_json_non_200_keeps_status(self):
        route = build_route(
            "GET", "/api/x",
            [{"status": 500, "body": "boom", "content_type": "text/plain"}],
            "get_api_x",
        )
        assert "status_code=500" in route
        resp = _serve(route, "GET", "/api/x")
        assert resp.status_code == 500
        assert resp.text == "boom"

    def test_xml_content_type_replayed(self):
        route = build_route(
            "GET", "/api/x",
            [{"status": 200, "body": "<a>1</a>", "content_type": "application/xml"}],
            "get_api_x",
        )
        resp = _serve(route, "GET", "/api/x")
        assert resp.text == "<a>1</a>"
        assert resp.headers["content-type"].startswith("application/xml")

    def test_json_body_still_returns_a_python_object(self):
        # Regression: JSON must keep the object-return path. Wrapping it in
        # Response would drop FastAPI's serialisation of nested values.
        route = build_route(
            "GET", "/api/j",
            [{"status": 200, "body": '{"a": 1}', "content_type": "application/json"}],
            "get_api_j",
        )
        assert 'return {"a": 1}' in route
        assert "Response(" not in route
        resp = _serve(route, "GET", "/api/j")
        assert resp.json() == {"a": 1}

    def test_missing_content_type_stays_json(self):
        route = build_route(
            "GET", "/api/j",
            [{"status": 200, "body": '{"a": 1}'}],
            "get_api_j",
        )
        assert "Response(" not in route
        assert _serve(route, "GET", "/api/j").json() == {"a": 1}

    def test_query_route_replays_non_json_body(self):
        responses = [
            {"status": 200, "body": "alpha", "content_type": "text/plain",
             "request": {"query_params": {"mode": "a"}}},
            {"status": 200, "body": "beta", "content_type": "text/plain",
             "request": {"query_params": {"mode": "b"}}},
        ]
        route = build_route(
            "GET", "/api/s", responses, "get_api_s",
            use_smart_fallback=True, sample_request={"query_params": {"mode": "a"}},
        )
        assert _serve(route, "GET", "/api/s", params={"mode": "b"}).text == "beta"
        assert _serve(route, "GET", "/api/s", params={"mode": "a"}).text == "alpha"

    def test_content_type_falls_back_to_content_mime_type(self, tmp_path):
        # Chrome records the type in content.mimeType; a HAR that omits the
        # response headers must still yield a type to replay the body under.
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/p",
                        "headers": [], "queryString": []},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "text/plain", "text": "plain text"}},
            "time": 10,
        }]}}
        f = tmp_path / "t.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        endpoints = HARParser(str(f)).get_endpoints()
        assert endpoints[0].responses[0].content_type == "text/plain"

    def test_header_content_type_wins_over_mime_type(self, tmp_path):
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/p",
                        "headers": [], "queryString": []},
            "response": {"status": 200,
                         "headers": [{"name": "Content-Type", "value": "text/csv"}],
                         "content": {"mimeType": "text/plain", "text": "a,b"}},
            "time": 10,
        }]}}
        f = tmp_path / "t.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        endpoints = HARParser(str(f)).get_endpoints()
        assert endpoints[0].responses[0].content_type == "text/csv"

    def test_end_to_end_text_plain_through_generator(self, tmp_path):
        # Full path: HAR -> parse -> generate -> serve. The mock must answer
        # the recorded bytes and type, not a JSON-quoted copy.
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/p",
                        "headers": [], "queryString": []},
            "response": {"status": 200,
                         "headers": [{"name": "Content-Type", "value": "text/plain"}],
                         "content": {"mimeType": "text/plain", "text": "plain text"}},
            "time": 10,
        }]}}
        f = tmp_path / "t.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()
        route = MockGenerator(use_smart_fallback=False).generate_endpoint(
            data["endpoints"][0]
        ).generated_code

        resp = _serve(route, "GET", "/p")
        assert resp.status_code == 200, resp.text
        assert resp.text == "plain text", resp.text
        assert resp.headers["content-type"].startswith("text/plain")


class TestResponseHeaderReplay:
    """Recorded response headers must reach the client, minus the server's own.

    Dropping them made a mocked 302 carry no Location and a mocked login set
    no cookie, so a client that followed the redirect or depended on the
    session cookie could not be exercised against the mock at all.
    """

    def _resp(self, status=200, body='{"ok": 1}', content_type="application/json",
              headers=None):
        r = {"status": status, "body": body, "content_type": content_type}
        if headers is not None:
            r["headers"] = headers
        return r

    def test_redirect_location_is_replayed(self):
        route = build_route(
            "GET", "/old",
            [self._resp(302, "", "text/plain", {"location": "/new"})],
            "get_old",
        )
        assert '"location": "/new"' in route
        resp = _serve(route, "GET", "/old", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/new"

    def test_set_cookie_and_etag_are_replayed(self):
        route = build_route(
            "GET", "/login",
            [self._resp(headers={
                "set-cookie": "sid=abc; HttpOnly",
                "etag": 'W/"v1"',
                "cache-control": "max-age=60",
                "x-request-id": "rid-1",
            })],
            "get_login",
        )
        resp = _serve(route, "GET", "/login")
        assert resp.status_code == 200
        assert resp.headers["set-cookie"] == "sid=abc; HttpOnly"
        assert resp.headers["etag"] == 'W/"v1"'
        assert resp.headers["cache-control"] == "max-age=60"
        assert resp.headers["x-request-id"] == "rid-1"

    def test_managed_headers_are_not_replayed(self):
        # Content-Length is recomputed, Content-Encoding would claim an
        # encoding the stored (decoded) body no longer has, Content-Type comes
        # from the media type, Date/Server are the server's, the hop-by-hop
        # ones belong to the transport and the CORS pair to the middleware.
        route = build_route(
            "GET", "/x",
            [self._resp(headers={
                "content-length": "999",
                "content-encoding": "gzip",
                "content-type": "application/json",
                "date": "Mon, 01 Jan 1990 00:00:00 GMT",
                "server": "nginx",
                "transfer-encoding": "chunked",
                "connection": "keep-alive",
                "access-control-allow-origin": "https://evil.example",
            })],
            "get_x",
        )
        assert "headers=" not in route

        resp = _serve(route, "GET", "/x")
        assert resp.headers["content-length"] != "999"      # recomputed
        assert resp.headers["content-length"] == str(len(resp.content))
        assert "content-encoding" not in resp.headers       # no gzip lie
        assert resp.headers["content-type"] == "application/json"

    def test_invalid_header_name_is_skipped(self):
        # A field name with a space is not an RFC 7230 token; Starlette would
        # reject the response outright.
        route = build_route(
            "GET", "/x",
            [self._resp(headers={"Bad Header": "x", "x-ok": "fine"})],
            "get_x",
        )
        assert '"bad header"' not in route
        assert '"x-ok": "fine"' in route
        resp = _serve(route, "GET", "/x")
        assert resp.headers["x-ok"] == "fine"

    def test_crlf_header_value_is_skipped(self):
        # A captured value carrying CRLF would let a header smuggle a second
        # one onto the wire.
        route = build_route(
            "GET", "/x",
            [self._resp(headers={"x-smuggle": "a\r\nX-Evil: 1", "x-ok": "fine"})],
            "get_x",
        )
        assert "x-smuggle" not in route
        resp = _serve(route, "GET", "/x")
        assert resp.headers.get("x-evil") is None
        assert resp.headers["x-ok"] == "fine"

    def test_header_value_with_quotes_compiles_and_serves(self):
        # ETag is W/"v1"; the literal must be escaped or the module will not
        # even parse.
        route = build_route(
            "GET", "/x", [self._resp(headers={"etag": 'W/"v1"'})], "get_x",
        )
        compile(route, "<route>", "exec")
        assert _serve(route, "GET", "/x").headers["etag"] == 'W/"v1"'

    def test_no_replayable_headers_keeps_the_bare_return(self):
        # Regression: an endpoint whose HAR recorded only managed headers must
        # keep emitting exactly the code it did before.
        route = build_route(
            "GET", "/x",
            [self._resp(201, headers={"content-type": "application/json"})],
            "get_x",
        )
        assert route.strip().endswith('return JSONResponse(status_code=201, content={"ok": 1})')

    def test_non_json_response_carries_headers(self):
        route = build_route(
            "GET", "/old",
            [self._resp(302, "", "text/plain",
                        {"location": "/new", "retry-after": "5"})],
            "get_old",
        )
        assert "media_type=" in route and "headers=" in route
        resp = _serve(route, "GET", "/old", follow_redirects=False)
        assert resp.headers["location"] == "/new"
        assert resp.headers["retry-after"] == "5"

    def test_query_route_replays_headers_per_branch(self):
        responses = [
            self._resp(body='{"m": "a"}', headers={"x-mode": "a"},
                       content_type="application/json") | {"request": {"query_params": {"mode": "a"}}},
            self._resp(body='{"m": "b"}', headers={"x-mode": "b"},
                       content_type="application/json") | {"request": {"query_params": {"mode": "b"}}},
        ]
        route = build_route(
            "GET", "/q", responses, "get_q",
            use_smart_fallback=True, sample_request={"query_params": {"mode": "a"}},
        )
        assert _serve(route, "GET", "/q", params={"mode": "b"}).headers["x-mode"] == "b"
        assert _serve(route, "GET", "/q", params={"mode": "a"}).headers["x-mode"] == "a"

    def test_smart_body_route_replays_headers(self):
        responses = [
            {"status": 200, "body": '{"access": "full"}',
             "request": {"body": '{"role": "admin"}'}, "headers": {"x-role": "admin"}},
            {"status": 403, "body": '{"access": "none"}',
             "request": {"body": '{"role": "guest"}'}, "headers": {"x-role": "guest"}},
        ]
        route = build_route("POST", "/r", responses, "post_r", use_smart_fallback=True)
        denied = _serve(route, "POST", "/r", json={"role": "guest"})
        assert denied.status_code == 403
        assert denied.headers["x-role"] == "guest"

    def test_bytes_bodies_and_headers_round_trip_end_to_end(self, tmp_path):
        # Full path through the parser: a recorded redirect HAR keeps its
        # Location on the generated mock.
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/old",
                        "headers": [], "queryString": []},
            "response": {"status": 302,
                         "headers": [{"name": "Location", "value": "https://api.example.com/new"},
                                     {"name": "Set-Cookie", "value": "sid=abc"},
                                     {"name": "Content-Length", "value": "0"}],
                         "content": {"mimeType": "text/plain", "text": ""}},
            "time": 10,
        }]}}
        f = tmp_path / "t.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()
        route = MockGenerator(use_smart_fallback=False).generate_endpoint(
            data["endpoints"][0]
        ).generated_code

        resp = _serve(route, "GET", "/old", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "https://api.example.com/new"
        assert resp.headers["set-cookie"] == "sid=abc"


class TestNonFiniteFloats:
    """A recorded NaN/Infinity must not turn the endpoint into a 500.

    json.loads accepts them; the JSON spec does not, and Starlette serialises
    with allow_nan=False. _py_literal rendered them with repr() -- the *names*
    nan/inf -- so the handler raised NameError, and handing the value back as
    a Python object failed inside JSONResponse even once the literal parsed.
    """

    @pytest.mark.parametrize("body, expected", [
        ('{"v": NaN}', '{"v": float("nan")}'),
        ('{"v": Infinity}', '{"v": float("inf")}'),
        ('{"v": -Infinity}', '{"v": float("-inf")}'),
    ])
    def test_non_finite_literals_name_a_value_not_a_bare_name(self, body, expected):
        literal = body_literal(body)
        assert literal == expected
        # The point is the runtime lookup, so exec it rather than compile it.
        namespace: dict = {"float": float}
        exec(f"value = {literal}", namespace)  # must not raise NameError

    @pytest.mark.parametrize("body", [
        '{"v": NaN}', '{"v": Infinity}', '{"a": [1, NaN]}',
    ])
    def test_recorded_non_finite_body_is_replayed_verbatim(self, body):
        route = build_route(
            "GET", "/v",
            [{"status": 200, "body": body, "content_type": "application/json"}],
            "get_v",
        )
        assert "Response(content=" in route

        resp = _serve(route, "GET", "/v")
        assert resp.status_code == 200, resp.text
        assert resp.text == body          # byte-for-byte, NaN included
        assert resp.headers["content-type"].startswith("application/json")

    def test_finite_json_is_still_an_object_return(self):
        route = build_route("GET", "/v", [{"status": 200, "body": '{"v": 1.5}'}], "get_v")
        assert 'return {"v": 1.5}' in route
        assert _serve(route, "GET", "/v").json() == {"v": 1.5}

    def test_smart_condition_with_a_non_finite_value_does_not_raise(self):
        responses = [
            {"status": 200, "body": '{"p": "a"}', "request": {"body": '{"v": NaN}'}},
            {"status": 200, "body": '{"p": "b"}', "request": {"body": '{"v": 1}'}},
        ]
        route = build_route("POST", "/v", responses, "post_v", use_smart_fallback=True)
        assert 'float("nan")' in route

        resp = _serve(route, "POST", "/v", json={"v": 1})
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"p": "b"}

    def test_non_finite_body_round_trips_through_the_parser(self, tmp_path):
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/v",
                        "headers": [], "queryString": []},
            "response": {"status": 200,
                         "headers": [{"name": "Content-Type", "value": "application/json"}],
                         "content": {"mimeType": "application/json", "text": '{"v": NaN}'}},
            "time": 10,
        }]}}
        f = tmp_path / "t.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()
        route = MockGenerator(use_smart_fallback=False).generate_endpoint(
            data["endpoints"][0]
        ).generated_code

        resp = _serve(route, "GET", "/v")
        assert resp.status_code == 200, resp.text
        assert resp.text == '{"v": NaN}'


class TestGeneratedMiddlewareStack:
    """The generated server must answer in a form a browser can read.

    Starlette makes the *last* registered middleware the outermost one, so
    registering CORS first left it innermost -- behind the resilience
    middleware. Those answer 400/429 before CORS ever runs, and a browser
    cannot read a response that arrives without the CORS headers: it reports
    a cross-origin failure instead of the status the mock meant to send.
    """

    def _app(self):
        src = _get_mock_server_header() + (
            '@app.get("/api/users")\n'
            'async def get_api_users():\n'
            '    """probe."""\n'
            '    return {"ok": 1}\n'
        )
        namespace: dict = {}
        exec(compile(src, "<generated>", "exec"), namespace)
        return namespace["app"]

    def test_cors_is_registered_last_so_it_is_outermost(self):
        from fastapi.middleware.cors import CORSMiddleware

        app = self._app()
        assert getattr(app.user_middleware[0], "cls", None) is CORSMiddleware

    def test_rate_limit_response_carries_cors_headers(self):
        from fastapi.testclient import TestClient

        app = self._app()
        origin = {"Origin": "http://localhost:3000"}
        with TestClient(app, raise_server_exceptions=False) as c:
            last = None
            for _ in range(70):
                last = c.get("/api/users", headers=origin)
                if last.status_code == 429:
                    break
            assert last.status_code == 429
            assert last.headers.get("access-control-allow-origin") == "*"

    def test_traversal_rejection_carries_cors_headers(self):
        from fastapi.testclient import TestClient

        app = self._app()
        with TestClient(app, raise_server_exceptions=False) as c:
            r = c.get("/a/%2e%2e/b", headers={"Origin": "http://localhost:3000"})
            assert r.status_code == 400
            assert r.headers.get("access-control-allow-origin") == "*"

    def test_preflight_does_not_spend_the_rate_limit_budget(self):
        # CORS outermost answers the preflight itself, so it never reaches the
        # counter; otherwise a browser client burns its budget on preflights.
        from fastapi.testclient import TestClient

        app = self._app()
        with TestClient(app, raise_server_exceptions=False) as c:
            for _ in range(10):
                c.options("/api/users", headers={
                    "Origin": "http://x.test",
                    "Access-Control-Request-Method": "GET",
                })
            for i in range(60):
                resp = c.get("/api/users")
                assert resp.status_code == 200, f"request {i + 1} refused early"
            assert c.get("/api/users").status_code == 429


class TestRepeatedResponseHeaders:
    """A header name may appear more than once, and both values must survive.

    Set-Cookie is the case that matters: a login that sets a session cookie
    and a csrf cookie. Collapsing the HAR's header list into a dict kept only
    the last one, so the mock set one of the two. Starlette's
    ``Response(headers=...)`` takes a mapping and rejects a list value, so the
    response has to be built and the further values appended.
    """

    def _resp(self, headers, status=200, body='{"ok": 1}', content_type="application/json"):
        return {"status": status, "body": body, "content_type": content_type,
                "headers": dict(headers), "header_pairs": [list(p) for p in headers]}

    def test_every_value_of_a_repeated_header_is_replayed(self):
        route = build_route(
            "GET", "/login",
            [self._resp([
                ("set-cookie", "sid=abc; Path=/"),
                ("set-cookie", "csrf=zzz; Path=/"),
                ("etag", '"v1"'),
            ])],
            "get_login",
        )
        resp = _serve(route, "GET", "/login")
        assert resp.status_code == 200
        assert resp.headers.get_list("set-cookie") == ["sid=abc; Path=/", "csrf=zzz; Path=/"]
        assert resp.headers["etag"] == '"v1"'

    def test_the_single_value_output_is_unchanged(self):
        # Only a repeat needs the extra statements; everything else keeps the
        # one-line form it has always emitted.
        route = build_route(
            "GET", "/old",
            [self._resp([("location", "/new")], status=302, body="", content_type="text/plain")],
            "get_old",
        )
        assert route.strip().endswith(
            'return Response(status_code=302, content="", media_type="text/plain", '
            'headers={"location": "/new"})'
        )

    def test_the_extra_statements_land_inside_the_branch(self):
        responses = [
            self._resp([("set-cookie", "a=1"), ("set-cookie", "b=2")]) | {
                "request": {"body": '{"role": "admin"}'},
            },
            {"status": 403, "body": '{"a": "none"}', "request": {"body": '{"role": "guest"}'}},
        ]
        route = build_route("POST", "/r", responses, "post_r", use_smart_fallback=True)

        # Eight spaces: the body of the if, not the function.
        assert '\n        _response = JSONResponse(content={"ok": 1}' in route
        assert '\n        _response.headers.append("set-cookie", "b=2")\n' in route
        assert '\n        return _response\n' in route

        resp = _serve(route, "POST", "/r", json={"role": "admin"})
        assert resp.status_code == 200
        assert resp.headers.get_list("set-cookie") == ["a=1", "b=2"]

    def test_a_repeated_header_on_a_non_json_response(self):
        route = build_route(
            "GET", "/old",
            [self._resp(
                [("location", "/new"), ("set-cookie", "a=1"), ("set-cookie", "b=2")],
                status=302, body="", content_type="text/plain",
            )],
            "get_old",
        )
        resp = _serve(route, "GET", "/old", follow_redirects=False)
        assert resp.status_code == 302
        assert resp.headers["location"] == "/new"
        assert resp.headers.get_list("set-cookie") == ["a=1", "b=2"]

    def test_a_repeated_managed_header_is_still_dropped(self):
        route = build_route(
            "GET", "/x",
            [self._resp([("content-length", "999"), ("content-length", "1000"), ("x-ok", "v")])],
            "get_x",
        )
        assert "content-length" not in route
        assert "headers.append" not in route    # nothing left to repeat
        assert _serve(route, "GET", "/x").headers["content-length"] != "999"

    def test_parser_keeps_order_and_repeats_while_the_dict_stays_lossy(self, tmp_path):
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/login",
                        "headers": [], "queryString": []},
            "response": {"status": 200,
                         "headers": [{"name": "Set-Cookie", "value": "sid=1"},
                                     {"name": "ETag", "value": '"v1"'},
                                     {"name": "Set-Cookie", "value": "csrf=2"}],
                         "content": {"mimeType": "application/json", "text": '{"ok": 1}'}},
            "time": 10,
        }]}}
        f = tmp_path / "t.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        sample = HARParser(str(f)).export_as_dict()["endpoints"][0]["sample_responses"][0]

        assert sample["header_pairs"] == [
            ["set-cookie", "sid=1"], ["etag", '"v1"'], ["set-cookie", "csrf=2"],
        ]
        # The dict is the older, lossy view the dashboard and JSON API expose.
        assert sample["headers"] == {"set-cookie": "csrf=2", "etag": '"v1"'}

    def test_repeated_cookies_round_trip_through_the_generator(self, tmp_path):
        har = {"log": {"version": "1.2", "entries": [{
            "request": {"method": "GET", "url": "https://api.example.com/login",
                        "headers": [], "queryString": []},
            "response": {"status": 200,
                         "headers": [{"name": "Set-Cookie", "value": "sid=1"},
                                     {"name": "Set-Cookie", "value": "csrf=2"}],
                         "content": {"mimeType": "application/json", "text": '{"ok": 1}'}},
            "time": 10,
        }]}}
        f = tmp_path / "t.har"
        f.write_text(json.dumps(har), encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()
        route = MockGenerator(use_smart_fallback=False).generate_endpoint(
            data["endpoints"][0]
        ).generated_code

        resp = _serve(route, "GET", "/login")
        assert resp.headers.get_list("set-cookie") == ["sid=1", "csrf=2"]


class TestBuiltinRouteSkip:
    """Only the builtin's own method is taken; the path is not enough.

    The generated header registers /health and /mockclaw/info as GET routes.
    Skipping by path alone silently dropped a capture of POST /health, and the
    mock then answered 405 to a request whose recording said 200.
    """

    def _entry(self, method, url, body='{"ok": 1}'):
        return {
            "request": {"method": method, "url": url, "headers": [], "queryString": []},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json", "text": body}},
            "time": 10,
        }

    def _generate(self, tmp_path, entries):
        f = tmp_path / "t.har"
        f.write_text(json.dumps({"log": {"version": "1.2", "entries": entries}}),
                     encoding="utf-8")
        data = HARParser(str(f)).export_as_dict()
        out = tmp_path / "mocks"
        MockGenerator(use_smart_fallback=False).generate_all(data["endpoints"], str(out))
        return (out / "dynamic_api.py").read_text(encoding="utf-8")

    def test_the_builtin_get_health_is_kept_once(self, tmp_path):
        src = self._generate(tmp_path, [
            self._entry("GET", "https://api.example.com/health", '{"captured": true}'),
        ])
        assert src.count('@app.get("/health")') == 1
        assert "captured" not in src

    def test_a_captured_post_health_is_still_mocked(self, tmp_path):
        src = self._generate(tmp_path, [
            self._entry("POST", "https://api.example.com/health", '{"probe": "post"}'),
        ])
        assert '@app.post("/health")' in src
        assert '{"probe": "post"}' in src

    def test_both_methods_of_the_same_builtin_path_coexist(self, tmp_path):
        src = self._generate(tmp_path, [
            self._entry("GET", "https://api.example.com/health", '{"captured": true}'),
            self._entry("POST", "https://api.example.com/health", '{"probe": "post"}'),
        ])
        assert src.count('@app.get("/health")') == 1      # the builtin, not the capture
        assert src.count('@app.post("/health")') == 1
        assert '{"probe": "post"}' in src

    def test_mockclaw_info_follows_the_same_rule(self, tmp_path):
        src = self._generate(tmp_path, [
            self._entry("GET", "https://api.example.com/mockclaw/info", '{"captured": true}'),
            self._entry("POST", "https://api.example.com/mockclaw/info", '{"probe": "post"}'),
        ])
        assert src.count('@app.get("/mockclaw/info")') == 1
        assert src.count('@app.post("/mockclaw/info")') == 1
        assert '{"probe": "post"}' in src

    def test_a_lowercase_method_still_matches_the_builtin(self, tmp_path):
        # The parser normalises, but generate_all also takes hand-built data.
        src = self._generate(tmp_path, [
            self._entry("get", "https://api.example.com/health", '{"captured": true}'),
        ])
        assert "captured" not in src


class TestPromptBody:
    """The prompt says what was recorded, and stays a workable size."""

    def _prompt(self, tmp_path, entries):
        f = tmp_path / "t.har"
        f.write_text(json.dumps({"log": {"version": "1.2", "entries": entries}}),
                     encoding="utf-8")
        return PromptBuilder().build_prompt(
            HARParser(str(f)).export_as_dict()["endpoints"][0]
        )

    @staticmethod
    def _entry(response_text=None, response_mime="application/json"):
        return {
            "request": {"method": "DELETE", "url": "https://api.example.com/api/x",
                        "headers": [], "queryString": []},
            "response": {"status": 204 if response_text is None else 200, "headers": [],
                         "content": {"mimeType": response_mime, "text": response_text}},
            "time": 10,
        }

    def test_a_missing_body_is_not_rendered_as_none(self, tmp_path):
        # A 204 carries no body and the parser stores None for it. Asking for
        # it with get('body', 'N/A') printed the literal None, because the key
        # exists and only a missing key takes the default.
        prompt = self._prompt(tmp_path, [self._entry()])

        assert prompt.count("- Body: N/A") == 2
        assert "None" not in prompt

    def test_a_large_body_is_capped_and_says_so(self, tmp_path):
        body = json.dumps({"items": [{"id": i, "name": "x" * 40} for i in range(4000)]})
        prompt = self._prompt(tmp_path, [self._entry(body)])

        assert len(prompt) < _MAX_BODY_CHARS + 500
        assert f"{len(body)} characters recorded" in prompt

    def test_a_body_within_the_cap_is_passed_through(self, tmp_path):
        prompt = self._prompt(tmp_path, [self._entry('{"ok": true}')])

        assert '{"ok": true}' in prompt
        assert "truncated" not in prompt


class TestEntriesWithoutAUrl:
    """An entry with no request url has no path to mock.

    The guard in parse() already dropped entries that are not objects, because
    coercing one to {} fabricates a bogus "GET /". An object whose request was
    null, missing or carried an empty url got through the same way:
    _extract_url_path("") is "/", and when the archive also held a real root
    entry the phantom was merged into it, its body landing as the first
    scenario. The mock then answered the junk entry for "/".
    """

    def _parse(self, tmp_path, entries):
        f = tmp_path / "t.har"
        f.write_text(json.dumps({"log": {"version": "1.2", "entries": entries}}),
                     encoding="utf-8")
        return HARParser(str(f)).export_as_dict()

    @staticmethod
    def _good(url, body='{"real": true}'):
        return {
            "request": {"method": "GET", "url": url, "headers": [], "queryString": []},
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json", "text": body}},
            "time": 10,
        }

    @staticmethod
    def _without_url(request, body='{"phantom": 1}'):
        return {
            "request": request,
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json", "text": body}},
            "time": 10,
        }

    @pytest.mark.parametrize("raw_request", [
        None,
        {"method": "GET", "headers": [], "queryString": []},
        {"method": "GET", "url": "", "headers": [], "queryString": []},
        {"method": "GET", "url": "   ", "headers": [], "queryString": []},
    ])
    def test_it_is_dropped(self, tmp_path, raw_request):
        assert self._parse(tmp_path, [self._without_url(raw_request)])["endpoints"] == []

    def test_it_does_not_merge_into_a_real_root_entry(self, tmp_path):
        data = self._parse(tmp_path, [
            self._without_url(None),
            self._good("https://api.example.com/"),
        ])

        assert len(data["endpoints"]) == 1
        endpoint = data["endpoints"][0]
        assert endpoint["resource_path"] == "/"
        assert [r["body"] for r in endpoint["sample_responses"]] == ["{\"real\": true}"]

    def test_a_relative_url_is_still_kept(self, tmp_path):
        data = self._parse(tmp_path, [self._good("/api/rel")])

        assert [e["resource_path"] for e in data["endpoints"]] == ["/api/rel"]


class TestRecordedTextIsNotSource:
    """Recorded bytes reach the generated file as data, never as code.

    A capture whose URL carried %22 decodes to a quote, and the decorator came
    out as ``@app.get("/api/a"b")`` -- an unterminated literal took the whole
    module down. A backslash was quieter and worse: ``\\b`` is the backspace
    escape, so the route compiled and then matched nothing. A request-body key
    holding a quote broke a smart-route condition the same way, and a path
    with a line break ended the ``# METHOD path`` comment and left the rest as
    a bare statement at module level.
    """

    def _entry(self, url, method="GET", body='{"ok": 1}', post=None):
        request = {"method": method, "url": url, "headers": [], "queryString": []}
        if post is not None:
            request["postData"] = {"mimeType": "application/json", "text": post}
        return {
            "request": request,
            "response": {"status": 200, "headers": [],
                         "content": {"mimeType": "application/json", "text": body}},
            "time": 10,
        }

    def _endpoint(self, tmp_path, entries):
        f = tmp_path / "t.har"
        f.write_text(json.dumps({"log": {"version": "1.2", "entries": entries}}),
                     encoding="utf-8")
        return HARParser(str(f)).export_as_dict()["endpoints"][0]

    @pytest.mark.parametrize("url, expected_path", [
        ("https://api.example.com/api/a%22b", "/api/a\"b"),
        ("https://api.example.com/api/a%5Cb", "/api/a\\b"),
        ("https://api.example.com/api/a%0Ab", "/api/a\nb"),
        ("https://api.example.com/api/a%09b", "/api/a\tb"),
    ])
    def test_the_recorded_path_survives_as_a_string(self, tmp_path, url, expected_path):
        endpoint = self._endpoint(tmp_path, [self._entry(url)])
        route = MockGenerator(use_smart_fallback=False).generate_endpoint(
            endpoint
        ).generated_code

        app, _ = _exec_route(route)
        assert [r.path for r in app.routes if r.path.startswith("/api/")] == [expected_path]

    def test_a_normal_path_is_emitted_exactly_as_before(self, tmp_path):
        endpoint = self._endpoint(tmp_path, [
            self._entry("https://api.example.com/api/users/1"),
        ])
        route = MockGenerator(use_smart_fallback=False).generate_endpoint(
            endpoint
        ).generated_code
        assert '@app.get("/api/users/{id}")' in route

    def test_a_line_break_in_the_path_does_not_end_the_comment(self, tmp_path):
        endpoint = self._endpoint(tmp_path, [
            self._entry("https://api.example.com/api/a%0Ab"),
        ])
        out = tmp_path / "mocks"
        MockGenerator(use_smart_fallback=False).generate_all([endpoint], str(out))
        source = (out / "dynamic_api.py").read_text(encoding="utf-8")

        # Importing the whole module is the check: an unflattened comment left
        # the remainder of the path as a bare statement at module level.
        namespace: dict = {}
        exec(compile(source, "<generated>", "exec"), namespace)
        assert "app" in namespace

    def test_a_quote_in_a_body_key_does_not_break_the_smart_route(self, tmp_path):
        weird = json.dumps({'a"b': 1})
        endpoint = self._endpoint(tmp_path, [
            self._entry("https://api.example.com/api/r", "POST", '{"x": 1}', post=weird),
            self._entry("https://api.example.com/api/r", "POST", '{"x": 2}',
                        post=json.dumps({'a"b': 2})),
        ])
        route = MockGenerator(use_smart_fallback=True).generate_endpoint(
            endpoint
        ).generated_code

        assert 'body.get("a\\"b")' in route
        resp = _serve(route, "POST", "/api/r", json={'a"b': 2})
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"x": 2}


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


class TestPathAndQueryDeclaration:
    """Path placeholders and recorded query keys must become typed handler args.

    Without declaration the OpenAPI schema advertises a bare endpoint:
    /docs shows no parameters and generated clients drop them entirely.
    Path params also must not carry a fake default -- FastAPI asserts
    ``Path`` params have none, and the URL always supplies the value.
    """

    def test_default_mode_declares_path_and_query_params(self):
        # The signature used to be empty: /api/user/{id} plus ?active=true
        # rendered as `async def get_api_user_id():`.
        responses = [
            {"status": 200, "body": '{"id": 1}',
             "request": {"query_params": {"active": "true"}}},
        ]
        route = build_route(
            "GET", "/api/user/{id}", responses, "get_api_user_id",
            sample_request={"query_params": {"active": "true"}},
        )
        assert "async def get_api_user_id(id: str, active: str = \"true\"):" in route

        resp = _serve(route, "GET", "/api/user/42")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {"id": 1}

        app, _ = _exec_route(route)
        params = app.openapi()["paths"]["/api/user/{id}"]["get"].get("parameters", [])
        by_name = {(p["name"], p["in"]) for p in params}
        assert ("id", "path") in by_name
        assert ("active", "query") in by_name

    def test_default_mode_multiple_path_placeholders(self):
        responses = [{"status": 201, "body": '{"placed": true}'}]
        route = build_route(
            "GET", "/api/user/{id}/orders/{order_id}", responses,
            "get_api_user_id_orders_order_id",
        )
        assert "async def get_api_user_id_orders_order_id(id: str, order_id: str):" in route

        resp = _serve(route, "GET", "/api/user/7/orders/9")
        assert resp.status_code == 201, resp.text
        assert resp.json() == {"placed": True}

    def test_smart_body_route_declares_path_params(self):
        # Body-routing handlers need path args too, or FastAPI rejects the
        # request with "no path params were defined" once a placeholder
        # exists in the decorator path.
        responses = [
            {"status": 200, "body": '{"ok": true}', "request": {"body": '{"role": "admin"}'}},
            {"status": 403, "body": '{"ok": false}', "request": {"body": '{"role": "user"}'}},
        ]
        route = build_route(
            "POST", "/api/user/{id}/role", responses, "post_api_user_id_role",
            use_smart_fallback=True,
        )
        assert "async def post_api_user_id_role(request: Request, id: str):" in route

        ok = _serve(route, "POST", "/api/user/5/role", json={"role": "admin"})
        assert ok.status_code == 200, ok.text
        forbidden = _serve(route, "POST", "/api/user/5/role", json={"role": "user"})
        assert forbidden.status_code == 403, forbidden.text

    def test_smart_query_route_declares_path_params(self):
        responses = [
            {"status": 200, "body": '{"a": 1}',
             "request": {"query_params": {"active": "true"}}},
            {"status": 404, "body": '{"a": 2}',
             "request": {"query_params": {"active": "false"}}},
        ]
        route = build_route(
            "GET", "/api/user/{id}/items", responses, "get_api_user_id_items",
            use_smart_fallback=True, sample_request={"query_params": {"active": "true"}},
        )
        assert "async def get_api_user_id_items(id: str, active: str = \"true\"):" in route

        miss = _serve(route, "GET", "/api/user/3/items", params={"active": "false"})
        assert miss.status_code == 404, miss.text
        hit = _serve(route, "GET", "/api/user/3/items", params={"active": "true"})
        assert hit.status_code == 200, hit.text

    def test_reserved_name_path_param_gets_alias(self):
        # {status} would shadow the generated module's `status` import and
        # break status.HTTP_* references, so it must be renamed with an alias.
        route = build_route(
            "GET", "/api/sys/{status}", [{"status": 200, "body": "{}"}],
            "get_api_sys_status",
        )
        assert 'async def get_api_sys_status(status_: str = Path(..., alias="status")):' in route

        resp = _serve(route, "GET", "/api/sys/active")
        assert resp.status_code == 200, resp.text

        app, _ = _exec_route(route)
        params = app.openapi()["paths"]["/api/sys/{status}"]["get"].get("parameters", [])
        assert [(p["name"], p["in"]) for p in params] == [("status", "path")]

    def test_keyword_path_param_gets_alias(self):
        route = build_route(
            "GET", "/api/items/{class}", [{"status": 200, "body": "{}"}],
            "get_api_items_class",
        )
        assert 'async def get_api_items_class(class_: str = Path(..., alias="class")):' in route

        resp = _serve(route, "GET", "/api/items/tool")
        assert resp.status_code == 200, resp.text

    def test_route_without_params_keeps_empty_signature(self):
        route = build_route(
            "GET", "/api/health", [{"status": 200, "body": '{"ok": 1}'}],
            "get_api_health",
        )
        assert "async def get_api_health():" in route

        resp = _serve(route, "GET", "/api/health")
        assert resp.status_code == 200, resp.text

    def test_empty_response_route_still_declares_path_params(self):
        # The no-HAR-data branch must not regress either.
        route = build_route(
            "GET", "/api/user/{id}", [], "get_api_user_id",
            sample_request={"query_params": {"active": "true"}},
        )
        assert "async def get_api_user_id(id: str, active: str = \"true\"):" in route

        resp = _serve(route, "GET", "/api/user/9")
        assert resp.status_code == 200, resp.text
        assert resp.json() == {}


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


_LLM_ROUTE = '@app.get("/x")\nasync def get_x():\n    return {"from_llm": True}\n'
_LLM_ENDPOINT = {
    "method": "GET",
    "resource_path": "/x",
    "sample_request": {},
    "sample_responses": [{"status": 200, "body": '{"ok": true}'}],
}


def _llm_strategy(content, fallback=None):
    """Wire a fake OpenAI-compatible client into an LLM generation strategy."""

    class _FakeResponse:
        def __init__(self, content):
            message = type("M", (), {"content": content})()
            self.choices = [type("C", (), {"message": message})()]

    class _FakeClient:
        def __init__(self, content):
            completions = type(
                "Comp", (), {"create": lambda self, **kw: _FakeResponse(content)},
            )()
            self.chat = type("Chat", (), {"completions": completions})()

    class _FakeManager:
        def __init__(self, content):
            self._content = content

        def get_client(self):
            return _FakeClient(self._content)

        def call_with_retry(self, fn, *args, **kwargs):
            return fn(*args, **kwargs)

    return LLMGenerationStrategy(
        client_manager=_FakeManager(content),
        prompt_builder=PromptBuilder(),
        code_extractor=CodeExtractor(),
        fallback=fallback,
    )


class TestLLMCodeValidation:
    """LLM output that is not a usable route must never reach the mock file."""

    def test_valid_python(self):
        assert LLMGenerationStrategy._is_usable_route(
            "@app.get('/x')\nasync def x():\n    return {}\n"
        )

    def test_syntax_error(self):
        assert not LLMGenerationStrategy._is_usable_route("def broken(:\n")

    def test_empty_string(self):
        assert not LLMGenerationStrategy._is_usable_route("")

    def test_helper_only_snippet_is_rejected(self):
        # Compiles fine, registers nothing: accepting it silently drops the
        # endpoint (the mock answers 404) and discards the working template.
        assert not LLMGenerationStrategy._is_usable_route(
            "from fastapi import APIRouter\n\ndef helper():\n    return 1\n"
        )

    def test_router_decorator_and_add_api_route_are_routes(self):
        assert LLMGenerationStrategy._is_usable_route(
            '@router.get("/x")\nasync def x():\n    return {}\n'
        )
        assert LLMGenerationStrategy._is_usable_route(
            'app.add_api_route("/x", x, methods=["GET"])\n'
        )

    def test_reply_with_a_javascript_fence_still_yields_a_running_route(self):
        # The `javascript` tag used to leak in as a bare name, which compiles
        # and then NameErrors when the generated module is imported.
        strategy = _llm_strategy(
            "Here:\n```javascript\n" + _LLM_ROUTE + "```\n"
        )
        code = strategy.generate(dict(_LLM_ENDPOINT))
        assert "from_llm" in code, code
        assert code.splitlines()[0] == '@app.get("/x")', code
        _exec_route(code)  # must import without a stray name

    def test_helper_only_reply_falls_back_to_the_template(self):
        # Compiles, registers nothing: accepting it would drop the endpoint.
        strategy = _llm_strategy(
            "```python\nfrom fastapi import APIRouter\n```\n",
            fallback=TemplateGenerationStrategy(),
        )
        code = strategy.generate(dict(_LLM_ENDPOINT))
        assert "from_llm" not in code, code
        assert "@app.get" in code, code
        _exec_route(code)

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
