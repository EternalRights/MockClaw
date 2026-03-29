"""
MockClaw Smart Fallback Tests
S2-006: Verify smart fallback routing works correctly

These tests validate that generated mocks enforce business logic
WITHOUT requiring an LLM API key.
"""

import pytest
import sys
from pathlib import Path
from typing import Any, Dict
from unittest.mock import patch, MagicMock

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from fastapi.testclient import TestClient
from tests.conftest import (
    verify_endpoint_called,
    get_last_request_body,
    clear_tracker,
    mock_client
)


class TestSmartFallbackCouponLogic:
    """
    Test that the mock server correctly handles coupon validation.
    
    Critical Requirements:
    1. EXPIRED2026 coupon MUST return 400
    2. SAVE10 coupon MUST return 200
    3. No coupon MUST return 200 (default)
    4. All tests MUST pass WITHOUT LLM API key
    """
    
    @pytest.fixture
    def generated_mock_app(self):
        """
        Load the generated mock application.
        
        This fixture imports the dynamically generated mock code
        and returns the FastAPI app instance.
        """
        mock_path = Path(__file__).parent.parent / "generated_mocks" / "dynamic_api.py"
        
        if not mock_path.exists():
            pytest.skip(
                f"Generated mock not found at {mock_path}. "
                "Run 'mockclaw generate tests/gauntlet/flow.har' first."
            )
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("mock_app", mock_path)
        if spec is None or spec.loader is None:
            pytest.fail(f"Failed to load spec for {mock_path}")
        
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if not hasattr(module, "app"):
            pytest.fail("Generated module has no 'app' attribute")
        
        return module.app
    
    def test_expired_coupon_returns_400(
        self,
        generated_mock_app,
        mock_client
    ):
        """
        POST /checkout with EXPIRED2026 coupon MUST return 400.
        
        This is the CRITICAL business logic test.
        """
        # Use the actual app from generated mocks
        client = TestClient(generated_mock_app)
        clear_tracker()
        
        request_body = {
            "user_id": "user123",
            "coupon_code": "EXPIRED2026",
            "shipping_address": "123 Main St"
        }
        
        response = client.post("/checkout", json=request_body)
        
        # ASSERTION 1: Must return 400 (not 500, not 200)
        assert response.status_code == 400, (
            f"Expected 400 for expired coupon, got {response.status_code}. "
            "Business logic not enforced!"
        )
        
        # ASSERTION 2: Response must contain error message
        data = response.json()
        assert "error" in str(data).lower() or "detail" in str(data).lower(), (
            "Response should contain error information"
        )
        
        # Verify endpoint was called
        verify_endpoint_called("/checkout", times=1)
        
        # Verify request body was captured
        last_body = get_last_request_body("/checkout")
        assert last_body is not None
        assert last_body.get("coupon_code") == "EXPIRED2026"
    
    def test_valid_coupon_returns_200(
        self,
        generated_mock_app,
        mock_client
    ):
        """
        POST /checkout with SAVE10 coupon MUST return 200.
        
        This tests the happy path - valid coupon should succeed.
        """
        client = TestClient(generated_mock_app)
        clear_tracker()
        
        request_body = {
            "user_id": "user123",
            "coupon_code": "SAVE10",
            "shipping_address": "123 Main St"
        }
        
        response = client.post("/checkout", json=request_body)
        
        # This is the KEY TEST - currently will FAIL because generated
        # mock always returns 400. Once smart fallback is implemented,
        # this should pass.
        
        # ASSERTION: Must return 200 for valid coupon
        assert response.status_code == 200, (
            f"Expected 200 for valid coupon, got {response.status_code}. "
            "Mock should handle success case!"
        )
        
        # Response should contain order confirmation
        if response.status_code == 200:
            data = response.json()
            assert "order_id" in data or "status" in data, (
                "Success response should contain order info"
            )
        
        verify_endpoint_called("/checkout", times=1)
    
    def test_no_coupon_returns_200(
        self,
        generated_mock_app,
        mock_client
    ):
        """
        POST /checkout with no coupon MUST return 200 (default).
        
        This tests the default path - no coupon should succeed.
        """
        client = TestClient(generated_mock_app)
        clear_tracker()
        
        request_body = {
            "user_id": "user123",
            "shipping_address": "123 Main St"
        }
        
        response = client.post("/checkout", json=request_body)
        
        # ASSERTION: Must return 200 when no coupon provided
        assert response.status_code == 200, (
            f"Expected 200 for no coupon, got {response.status_code}. "
            "Default path should succeed!"
        )
        
        verify_endpoint_called("/checkout", times=1)
        
        # Verify the request had no coupon
        last_body = get_last_request_body("/checkout")
        assert last_body is not None
        assert "coupon_code" not in last_body or last_body.get("coupon_code") is None


class TestSmartFallbackRequestMatching:
    """
    Test that the smart fallback correctly matches requests to responses.
    
    This validates the routing logic that decides which response to return
    based on request characteristics.
    """
    
    @pytest.fixture
    def generated_mock_app(self):
        """Load generated mock app."""
        mock_path = Path(__file__).parent.parent / "generated_mocks" / "dynamic_api.py"
        
        if not mock_path.exists():
            pytest.skip(f"Generated mock not found at {mock_path}")
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("mock_app", mock_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if not hasattr(module, "app"):
            pytest.fail("Generated module has no 'app' attribute")
        
        return module.app
    
    def test_request_body_is_analyzed(
        self,
        generated_mock_app
    ):
        """
        Verify that request body is analyzed for routing decisions.
        
        The mock should inspect the coupon_code field and route accordingly.
        """
        client = TestClient(generated_mock_app)
        clear_tracker()
        
        # Send expired coupon
        response1 = client.post("/checkout", json={"coupon_code": "EXPIRED2026"})
        assert response1.status_code == 400
        
        # Send valid coupon
        response2 = client.post("/checkout", json={"coupon_code": "SAVE10"})
        # This will fail until smart fallback is implemented
        assert response2.status_code == 200, (
            "Smart fallback should route to success response"
        )
        
        # Verify both requests were tracked
        verify_endpoint_called("/checkout", times=2)
    
    def test_default_response_when_no_match(
        self,
        generated_mock_app
    ):
        """
        When no specific rule matches, return default (success) response.
        
        This is the "fallback" in smart fallback.
        """
        client = TestClient(generated_mock_app)
        clear_tracker()
        
        # Send unknown coupon code - should default to success
        response = client.post("/checkout", json={"coupon_code": "UNKNOWN_CODE"})
        
        # Should return 200 as default (no specific rule for UNKNOWN_CODE)
        assert response.status_code == 200, (
            "Unknown coupon should use default (success) response"
        )


class TestNoLLMRequirement:
    """
    Verify tests pass WITHOUT LLM API key.
    
    This is CRITICAL - the smart fallback must work offline.
    """
    
    def test_generated_mock_works_without_llm(
        self,
        generated_mock_app,
        no_llm_env
    ):
        """
        Generated mock must function without LLM API key.
        
        The smart fallback logic is rule-based, not LLM-dependent.
        """
        client = TestClient(generated_mock_app)
        clear_tracker()
        
        # This should work regardless of LLM configuration
        response = client.get("/health")
        assert response.status_code == 200
        
        # The mock was generated from HAR, doesn't need LLM at runtime
        data = response.json()
        assert data.get("status") == "OK" or data.get("status") == "ok"
    
    @patch.dict('os.environ', {'LLM_PROVIDER': 'none', 'LLM_API_KEY': ''}, clear=False)
    def test_generation_works_without_llm(
        self,
        sample_har_path,
        temp_output_dir
    ):
        """
        Mock generation must work without LLM API key.
        
        Uses rule-based generation when LLM is unavailable.
        """
        from core.generator import MockGenerator
        
        # Parse HAR
        from core.parser import HARParser
        parser = HARParser(str(sample_har_path))
        endpoints = parser.get_endpoints()
        
        assert len(endpoints) > 0, "HAR should have endpoints"
        
        # Generate without LLM
        generator = MockGenerator()
        
        # Convert endpoints
        endpoint_dicts = []
        for ep in endpoints:
            all_responses = [
                {"status": r.status, "body": r.body}
                for r in ep.responses
            ]
            endpoint_dicts.append({
                "id": f"ep_{ep.resource_path}_{ep.method}".replace("/", "_"),
                "resource_path": ep.resource_path,
                "method": ep.method,
                "sample_responses": all_responses,
                "sample_response": {
                    "status": ep.responses[0].status if ep.responses else 200,
                    "body": ep.responses[0].body if ep.responses else None
                },
            })
        
        results = generator.generate_all(endpoint_dicts, str(temp_output_dir))
        
        # Should generate successfully without LLM
        success_count = sum(1 for r in results if r.success)
        assert success_count > 0, (
            "Should generate at least one endpoint without LLM"
        )


class TestEdgeCases:
    """Test edge cases in smart fallback."""
    
    @pytest.fixture
    def generated_mock_app(self):
        """Load generated mock app."""
        mock_path = Path(__file__).parent.parent / "generated_mocks" / "dynamic_api.py"
        
        if not mock_path.exists():
            pytest.skip(f"Generated mock not found at {mock_path}")
        
        import importlib.util
        spec = importlib.util.spec_from_file_location("mock_app", mock_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        
        if not hasattr(module, "app"):
            pytest.fail("Generated module has no 'app' attribute")
        
        return module.app
    
    def test_empty_coupon_code(
        self,
        generated_mock_app
    ):
        """Test with empty string coupon."""
        client = TestClient(generated_mock_app)
        clear_tracker()
        
        response = client.post("/checkout", json={"coupon_code": ""})
        
        # Empty coupon should be treated as no coupon (success)
        assert response.status_code == 200, (
            "Empty coupon should use default response"
        )
    
    def test_null_coupon_code(
        self,
        generated_mock_app
    ):
        """Test with null coupon."""
        client = TestClient(generated_mock_app)
        clear_tracker()
        
        response = client.post("/checkout", json={"coupon_code": None})
        
        # Null coupon should succeed
        assert response.status_code == 200, (
            "Null coupon should use default response"
        )
    
    def test_case_sensitive_coupon(
        self,
        generated_mock_app
    ):
        """Test coupon code case sensitivity."""
        client = TestClient(generated_mock_app)
        clear_tracker()
        
        # Test lowercase (should not match EXPIRED2026)
        response = client.post("/checkout", json={"coupon_code": "expired2026"})
        
        # Should NOT match the uppercase version
        # (whether this succeeds or fails depends on implementation)
        # For now, just document the behavior
        print(f"Lowercase coupon response: {response.status_code}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
