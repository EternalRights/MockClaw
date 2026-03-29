"""Quick test of the mock server."""
import requests

BASE_URL = "http://localhost:8006"

print("=" * 60)
print("Testing MockClaw Generated Server")
print("=" * 60)

# Test 1: Health check
print("\n1. Health check...")
resp = requests.get(f"{BASE_URL}/health")
print(f"   Status: {resp.status_code}")
print(f"   Response: {resp.json()}")
assert resp.status_code == 200

# Test 2: Products endpoint
print("\n2. Get products...")
resp = requests.get(f"{BASE_URL}/products")
print(f"   Status: {resp.status_code}")
data = resp.json()
print(f"   Products count: {len(data.get('products', []))}")
assert resp.status_code == 200

# Test 3: Expired coupon (should return 400)
print("\n3. Checkout with EXPIRED coupon...")
resp = requests.post(f"{BASE_URL}/checkout", json={
    "user_id": "user123",
    "coupon_code": "EXPIRED2026",
    "shipping_address": "123 Main St"
})
print(f"   Status: {resp.status_code}")
print(f"   Response: {resp.json()}")
assert resp.status_code == 400, f"Expected 400 but got {resp.status_code}"

# Test 4: Valid coupon (should return 200)
print("\n4. Checkout with VALID coupon (SAVE10)...")
resp = requests.post(f"{BASE_URL}/checkout", json={
    "user_id": "user123",
    "coupon_code": "SAVE10",
    "shipping_address": "123 Main St"
})
print(f"   Status: {resp.status_code}")
print(f"   Response: {resp.json()}")
assert resp.status_code == 200, f"Expected 200 but got {resp.status_code}"

print("\n" + "=" * 60)
print("✅ ALL TESTS PASSED!")
print("=" * 60)
