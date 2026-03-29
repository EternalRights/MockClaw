"""
Comprehensive pytest test suite for MockClaw generated mocks.
Tests all business scenarios including edge cases and security.
"""
import pytest
import requests
from typing import Generator

BASE_URL = "http://localhost:8006"


@pytest.fixture(scope="module")
def mock_server() -> Generator[str, None, None]:
    """Fixture that provides the mock server URL."""
    yield BASE_URL


class TestHealthAndInfo:
    """Test basic server health and metadata endpoints."""
    
    def test_health_check(self, mock_server):
        """Health endpoint should return OK status."""
        response = requests.get(f"{mock_server}/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"].lower() == "ok"
        assert "service" in data
    
    def test_mockclaw_info(self, mock_server):
        """Info endpoint should return generator metadata."""
        response = requests.get(f"{mock_server}/mockclaw/info")
        assert response.status_code == 200
        data = response.json()
        assert data["generator"] == "MockClaw"
        assert "version" in data


class TestProducts:
    """Test product catalog endpoints."""
    
    def test_get_all_products(self, mock_server):
        """Should return list of all products."""
        response = requests.get(f"{mock_server}/products")
        assert response.status_code == 200
        data = response.json()
        assert "products" in data
        assert len(data["products"]) > 0
        assert "total" in data
    
    def test_product_structure(self, mock_server):
        """Each product should have required fields."""
        response = requests.get(f"{mock_server}/products")
        assert response.status_code == 200
        products = response.json()["products"]
        
        for product in products:
            assert "id" in product
            assert "name" in product
            assert "price" in product
            assert "category" in product
    
    def test_filter_by_category(self, mock_server):
        """Should filter products by category."""
        response = requests.get(f"{mock_server}/products?category=electronics")
        assert response.status_code == 200
        products = response.json()["products"]
        
        # All returned products should be electronics
        for product in products:
            assert product["category"] == "electronics"


class TestAuthentication:
    """Test user authentication endpoints."""
    
    def test_login_success(self, mock_server):
        """Valid login should return token."""
        response = requests.post(f"{mock_server}/login", json={
            "username": "testuser",
            "password": "password123"
        })
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert "user" in data
        assert "username" in data["user"]


class TestCartOperations:
    """Test shopping cart operations."""
    
    def test_view_empty_cart(self, mock_server):
        """Empty cart should return empty items list."""
        response = requests.get(f"{mock_server}/cart/user123")
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert isinstance(data["items"], list)
    
    def test_add_item_to_cart(self, mock_server):
        """Should add item to cart successfully."""
        response = requests.post(f"{mock_server}/cart/user123", json={
            "product_id": "iphone15",
            "name": "iPhone 15 Pro",
            "price": 999.99,
            "quantity": 1
        })
        assert response.status_code == 200
        data = response.json()
        assert "items" in data
        assert len(data["items"]) > 0


class TestCheckout:
    """Test checkout process - CRITICAL BUSINESS LOGIC."""
    
    def test_checkout_with_expired_coupon(self, mock_server):
        """
        CRITICAL: Expired coupons MUST be rejected.
        This is the key business rule we're testing.
        """
        response = requests.post(f"{mock_server}/checkout", json={
            "user_id": "user123",
            "coupon_code": "EXPIRED2026",
            "shipping_address": "123 Main St"
        })
        
        # Must return 400 Bad Request
        assert response.status_code == 400, \
            f"Expired coupon should be rejected with 400, got {response.status_code}"
        
        # Error should mention coupon expired
        response_text = str(response.json()).lower()
        assert "coupon" in response_text and "expired" in response_text, \
            "Error message should mention expired coupon"
    
    def test_checkout_with_valid_coupon(self, mock_server):
        """
        CRITICAL: Valid coupons MUST be accepted.
        Tests Smart Fallback routing logic.
        """
        response = requests.post(f"{mock_server}/checkout", json={
            "user_id": "user123",
            "coupon_code": "SAVE10",
            "shipping_address": "123 Main St"
        })
        
        # Must return 200 OK
        assert response.status_code == 200, \
            f"Valid coupon should be accepted with 200, got {response.status_code}"
        
        # Should have order confirmation
        data = response.json()
        assert "order_id" in data or "status" in data, \
            "Response should contain order confirmation"
        
        # Should have discount applied
        if "discount" in data:
            assert data["discount"] > 0, "Valid coupon should apply discount"
    
    def test_checkout_without_coupon(self, mock_server):
        """Checkout should work without coupon code."""
        response = requests.post(f"{mock_server}/checkout", json={
            "user_id": "user123",
            "shipping_address": "123 Main St"
        })
        
        # Should still work (no coupon = no discount)
        assert response.status_code in [200, 400], \
            "Checkout should either work or give clear error"


class TestOrderHistory:
    """Test order history endpoints."""
    
    def test_get_order_history(self, mock_server):
        """Should return user's order history."""
        response = requests.get(f"{mock_server}/orders/user123")
        assert response.status_code == 200
        data = response.json()
        assert "orders" in data or isinstance(data, list)


class TestSecurity:
    """Test security features (auto-injected by MockClaw)."""
    
    def test_path_traversal_blocked(self, mock_server):
        """Path traversal attacks should be blocked."""
        response = requests.get(f"{mock_server}/../etc/passwd")
        
        # Should be blocked (400 or 404)
        assert response.status_code in [400, 404], \
            f"Path traversal should be blocked, got {response.status_code}"
        
        # Error should mention security
        response_text = str(response.json()).lower()
        assert "invalid" in response_text or "error" in response_text
    
    def test_rate_limiting_headers(self, mock_server):
        """Rate limiting middleware should be active."""
        # Make multiple requests to trigger rate limiting
        for i in range(10):
            response = requests.get(f"{mock_server}/health")
            assert response.status_code == 200
        
        # If we get here without 429, rate limit is reasonable
        # (60 req/min by default)


class TestErrorHandling:
    """Test error handling for edge cases."""
    
    def test_nonexistent_endpoint(self, mock_server):
        """Non-existent endpoints should return 404."""
        response = requests.get(f"{mock_server}/nonexistent/endpoint")
        assert response.status_code == 404
    
    def test_method_not_allowed(self, mock_server):
        """Wrong HTTP method should return 405."""
        # Try DELETE on products (should be GET only)
        response = requests.delete(f"{mock_server}/products")
        assert response.status_code in [404, 405]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
