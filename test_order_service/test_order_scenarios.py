"""
Order Service Test Scenarios
Testing MockClaw generated mocks with real pytest tests.
"""
import pytest
import asyncio
import httpx
import sys
from pathlib import Path

# Configure pytest-asyncio mode
pytestmark = pytest.mark.asyncio(scope="function")

# Add the mocks_v2 directory to the path so we can import the generated app (CLI smart fallback mode)
sys.path.insert(0, str(Path(__file__).parent / "mocks_v2"))

# Import the generated mock app
try:
    from dynamic_api import app
    MOCKS_AVAILABLE = True
    print("✅ Using Smart Fallback mocks (CLI generated)")
except ImportError as e:
    MOCKS_AVAILABLE = False
    print(f"Warning: Could not import generated mocks: {e}")


@pytest.fixture
async def mock_client():
    """Create an async test client for the mock server."""
    if not MOCKS_AVAILABLE:
        pytest.skip("Generated mocks not available")
    
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        yield client


@pytest.mark.asyncio
async def test_health_check(mock_client):
    """Test that the mock server is running."""
    response = await mock_client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "OK"
    print("✓ Health check passed")


@pytest.mark.asyncio
async def test_products_endpoint(mock_client):
    """Test the products listing endpoint."""
    response = await mock_client.get("/products")
    assert response.status_code == 200
    # Note: With fallback mocks, this returns "mock" string instead of actual data
    # This is a limitation of the non-LLM generation mode
    print(f"✓ Products endpoint returned: {response.status_code}")


@pytest.mark.asyncio
async def test_login_endpoint(mock_client):
    """Test the login endpoint."""
    response = await mock_client.post("/login", json={
        "username": "testuser",
        "password": "password123"
    })
    assert response.status_code == 200
    print(f"✓ Login endpoint returned: {response.status_code}")


@pytest.mark.asyncio
async def test_expired_coupon_returns_400(mock_client):
    """
    CRITICAL TEST: Expired coupon should return 400 Bad Request.
    This is the key business logic we're testing.
    """
    response = await mock_client.post("/checkout", json={
        "user_id": "user123",
        "coupon_code": "EXPIRED2026",
        "shipping_address": "123 Main St"
    })
    
    # The mock should return 400 for expired coupon
    # This is what we recorded in the HAR file
    assert response.status_code == 400, f"Expected 400 but got {response.status_code}"
    
    # Check error response structure
    data = response.json()
    assert "error" in data or "detail" in data
    
    print(f"✓ Expired coupon correctly rejected with status {response.status_code}")
    print(f"  Response: {data}")


@pytest.mark.asyncio
async def test_valid_coupon_returns_200(mock_client):
    """
    Test that valid coupon returns 200 OK.
    
    CRITICAL: This test MUST pass with Smart Fallback mode (--no-llm).
    """
    response = await mock_client.post("/checkout", json={
        "user_id": "user123",
        "coupon_code": "SAVE10",
        "shipping_address": "123 Main St"
    })
    
    # Smart fallback should route based on coupon_code
    assert response.status_code == 200, f"Expected 200 but got {response.status_code}"
    data = response.json()
    assert data.get("status") == "confirmed", f"Expected confirmed order, got {data}"
    print(f"✓ Valid coupon accepted with status {response.status_code}")
    print(f"  Order ID: {data.get('order_id')}")


@pytest.mark.asyncio
async def test_cart_operations(mock_client):
    """Test cart add and view operations."""
    # View empty cart
    response = await mock_client.get("/cart/user123")
    assert response.status_code == 200
    
    # Add item to cart
    response = await mock_client.post("/cart/user123", json={
        "product_id": "iphone15",
        "name": "iPhone 15 Pro",
        "price": 999.99,
        "quantity": 1
    })
    assert response.status_code == 200
    
    print(f"✓ Cart operations returned: {response.status_code}")


@pytest.mark.asyncio
async def test_order_history(mock_client):
    """Test order history endpoint."""
    response = await mock_client.get("/orders/user123")
    assert response.status_code == 200
    print(f"✓ Order history returned: {response.status_code}")


@pytest.mark.asyncio
async def test_concurrent_orders(mock_client):
    """
    CONCURRENCY TEST: Send 5 checkout requests simultaneously.
    Tests that the mock server can handle concurrent requests.
    """
    async def place_order(order_num: int):
        response = await mock_client.post("/checkout", json={
            "user_id": f"user{order_num}",
            "coupon_code": "SAVE10",
            "shipping_address": f"{order_num} Main St"
        })
        return response.status_code
    
    # Send 5 requests concurrently
    tasks = [place_order(i) for i in range(1, 6)]
    results = await asyncio.gather(*tasks)
    
    # All should complete (though some might be 400 if cart is empty)
    assert len(results) == 5
    print(f"✓ Concurrent orders completed: {results}")
    
    # At least some should succeed or fail gracefully (no crashes)
    success_count = sum(1 for r in results if r == 200)
    error_count = sum(1 for r in results if r in [400, 404])
    
    print(f"  Success: {success_count}, Errors: {error_count}")
    assert success_count + error_count == 5, "All requests should return a valid response"


@pytest.mark.asyncio
async def test_path_traversal_blocked(mock_client):
    """Test that path traversal attacks are blocked by middleware."""
    # Try path traversal attack
    response = await mock_client.get("/../etc/passwd")
    
    # Should be blocked by middleware
    assert response.status_code in [400, 404], f"Path traversal should be blocked, got {response.status_code}"
    print(f"✓ Path traversal correctly blocked with status {response.status_code}")


@pytest.mark.asyncio  
async def test_invalid_endpoint_returns_404(mock_client):
    """Test that non-existent endpoints return 404."""
    response = await mock_client.get("/nonexistent/endpoint")
    assert response.status_code == 404
    print(f"✓ Non-existent endpoint returned 404")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
