"""
MockClaw Demo Tests
Quick verification that generated mocks work correctly.
Run with: pytest sample_data/test_demo.py -v
"""
import requests
import os

# Allow custom port via environment variable, default to 8000
BASE_URL = os.environ.get("MOCKCLAW_URL", "http://localhost:8000")


def test_health():
    """Test that mock server is running."""
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"].lower() == "ok"  # Case-insensitive
    print("✅ Health check passed")


def test_products():
    """Test products endpoint returns data."""
    response = requests.get(f"{BASE_URL}/products")
    assert response.status_code == 200
    data = response.json()
    assert "products" in data
    assert len(data["products"]) > 0
    print(f"✅ Products endpoint returned {len(data['products'])} products")


def test_checkout_with_expired_coupon():
    """
    CRITICAL TEST: Expired coupons must be rejected.
    
    This tests the Smart Fallback routing logic.
    """
    payload = {
        "user_id": "user123",
        "coupon_code": "EXPIRED2026",
        "shipping_address": "123 Main St"
    }
    response = requests.post(f"{BASE_URL}/checkout", json=payload)
    
    # Must return 400 Bad Request
    assert response.status_code == 400, f"Expected 400 but got {response.status_code}"
    
    # Error message should mention coupon expired
    response_text = str(response.json())
    assert "COUPON_EXPIRED" in response_text or "expired" in response_text.lower(), \
        f"Expected coupon expired error, got: {response.json()}"
    
    print(f"✅ Expired coupon correctly rejected (status {response.status_code})")


def test_checkout_with_valid_coupon():
    """
    CRITICAL TEST: Valid coupons should be accepted.
    
    This tests that Smart Fallback routes based on coupon_code field.
    """
    payload = {
        "user_id": "user123",
        "coupon_code": "SAVE10",
        "shipping_address": "123 Main St"
    }
    response = requests.post(f"{BASE_URL}/checkout", json=payload)
    
    # Must return 200 OK
    assert response.status_code == 200, f"Expected 200 but got {response.status_code}"
    
    # Response should have order confirmation
    data = response.json()
    assert "order_id" in data or "status" in data, \
        f"Expected order confirmation, got: {data}"
    
    print(f"✅ Valid coupon accepted (status {response.status_code}, order: {data.get('order_id', 'N/A')})")


if __name__ == "__main__":
    import sys
    
    print("=" * 60)
    print("MockClaw Demo Tests")
    print("=" * 60)
    print("\nTesting mock server at:", BASE_URL)
    print("Make sure server is running: mockclaw serve ./my_mocks\n")
    
    try:
        test_health()
        test_products()
        test_checkout_with_expired_coupon()
        test_checkout_with_valid_coupon()
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS PASSED!")
        print("=" * 60)
        sys.exit(0)
        
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}")
        sys.exit(1)
    except requests.exceptions.ConnectionError:
        print(f"\n❌ CONNECTION ERROR: Cannot connect to {BASE_URL}")
        print("   Make sure mock server is running:")
        print("   mockclaw serve ./my_mocks --port 8000")
        sys.exit(1)
