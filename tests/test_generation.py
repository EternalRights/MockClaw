"""
MockClaw Generation Tests
"""

import json

import pytest

from core.parser import HARParser
from core.generator import MockGenerator, GenerationResult
from core.route_builder import build_route, generate_func_name


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
