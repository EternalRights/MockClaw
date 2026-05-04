"""
MockClaw Gauntlet Recorder
Records realistic user traffic from the Dummy Shop API.
This creates the "flow.har" file for chaos testing.
"""

import json
import random
import requests
from pathlib import Path
from datetime import datetime, timezone
from typing import Any


class GauntletRecorder:
    """Records user sessions and exports as HAR file."""
    
    def __init__(self, base_url: str = "http://localhost:9000"):
        self.base_url = base_url
        self.entries: list[dict[str, Any]] = []
        self.session = requests.Session()
    
    def record_request(self, method: str, url: str, request_data: Any = None, 
                       response_data: Any = None, status_code: int = 200,
                       error: str = None):
        """Record a single request/response pair."""
        timestamp = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        
        entry = {
            "startedDateTime": timestamp,
            "time": random.randint(50, 500),
            "request": {
                "method": method,
                "url": url,
                "httpVersion": "HTTP/1.1",
                "headers": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "User-Agent", "value": "MockClaw-Gauntlet/1.0"}
                ],
                "queryString": [],
                "postData": None,
                "headersSize": 200,
                "bodySize": len(json.dumps(request_data)) if request_data is not None else 0
            },
            "response": {
                "status": status_code,
                "statusText": "OK" if status_code == 200 else "Error",
                "httpVersion": "HTTP/1.1",
                "headers": [
                    {"name": "Content-Type", "value": "application/json"}
                ],
                "content": {
                    "mimeType": "application/json",
                    "text": json.dumps(response_data) if response_data is not None else json.dumps({"error": error})
                },
                "redirectURL": "",
                "headersSize": 150,
                "bodySize": len(json.dumps(response_data)) if response_data is not None else 50
            },
            "cache": {},
            "timings": {"send": 10, "wait": random.randint(50, 200), "receive": 20}
        }
        
        if request_data is not None:
            entry["request"]["postData"] = {
                "mimeType": "application/json",
                "text": json.dumps(request_data)
            }
        
        self.entries.append(entry)
        return entry
    
    def run_user_session(self):
        """Simulate a complete user shopping session."""
        
        print("\n🛍️  Starting user shopping session...")
        
        # Step 1: Browse products
        print("  1. Browsing products...")
        try:
            resp = self.session.get(f"{self.base_url}/products")
            self.record_request(
                "GET", f"{self.base_url}/products",
                response_data=resp.json(),
                status_code=resp.status_code
            )
        except Exception as e:
            print(f"     Warning: {e}")
        
        # Step 2: Browse with category filter
        print("  2. Filtering by category...")
        try:
            resp = self.session.get(f"{self.base_url}/products?category=electronics")
            self.record_request(
                "GET", f"{self.base_url}/products?category=electronics",
                response_data=resp.json(),
                status_code=resp.status_code
            )
        except Exception as e:
            print(f"     Warning: {e}")
        
        # Step 3: Login
        print("  3. Logging in...")
        login_data = {"username": "testuser", "password": "password123"}
        try:
            resp = self.session.post(f"{self.base_url}/login", json=login_data)
            self.record_request(
                "POST", f"{self.base_url}/login",
                request_data=login_data,
                response_data=resp.json(),
                status_code=resp.status_code
            )
            token = resp.json().get("token") if resp.status_code == 200 else None
        except Exception as e:
            print(f"     Warning: {e}")
            token = None
        
        # Step 4: View cart (empty)
        print("  4. Viewing empty cart...")
        try:
            resp = self.session.get(f"{self.base_url}/cart/user123")
            self.record_request(
                "GET", f"{self.base_url}/cart/user123",
                response_data=resp.json(),
                status_code=resp.status_code
            )
        except Exception as e:
            print(f"     Warning: {e}")
        
        # Step 5: Add items to cart
        print("  5. Adding items to cart...")
        cart_items = [
            {"product_id": "iphone15", "name": "iPhone 15 Pro", "price": 999.99, "quantity": 1},
            {"product_id": "airpods", "name": "AirPods Pro", "price": 249.99, "quantity": 2},
        ]
        
        for item in cart_items:
            try:
                resp = self.session.post(f"{self.base_url}/cart/user123", json=item)
                self.record_request(
                    "POST", f"{self.base_url}/cart/user123",
                    request_data=item,
                    response_data=resp.json(),
                    status_code=resp.status_code
                )
            except Exception as e:
                print(f"     Warning: {e}")
        
        # Step 6: View cart with items
        print("  6. Viewing cart with items...")
        try:
            resp = self.session.get(f"{self.base_url}/cart/user123")
            self.record_request(
                "GET", f"{self.base_url}/cart/user123",
                response_data=resp.json(),
                status_code=resp.status_code
            )
        except Exception as e:
            print(f"     Warning: {e}")
        
        # Step 7: Try EXPIRED coupon (should fail) - THE CRITICAL TEST
        print("  7. Attempting checkout with EXPIRED coupon...")
        checkout_data = {
            "user_id": "user123",
            "coupon_code": "EXPIRED2026",  # This should return 400
            "shipping_address": "123 Main St"
        }
        try:
            resp = self.session.post(f"{self.base_url}/checkout", json=checkout_data)
            self.record_request(
                "POST", f"{self.base_url}/checkout",
                request_data=checkout_data,
                response_data=resp.json() if resp.text else {"error": "Checkout failed"},
                status_code=resp.status_code,  # Should be 400
                error="COUPON_EXPIRED" if resp.status_code == 400 else None
            )
            print(f"     ✓ Correctly rejected expired coupon (status {resp.status_code})")
        except Exception as e:
            print(f"     Warning: {e}")
        
        # Step 8: Try valid coupon (should succeed)
        print("  8. Attempting checkout with VALID coupon...")
        checkout_data["coupon_code"] = "SAVE10"
        try:
            resp = self.session.post(f"{self.base_url}/checkout", json=checkout_data)
            self.record_request(
                "POST", f"{self.base_url}/checkout",
                request_data=checkout_data,
                response_data=resp.json() if resp.text else {"error": "Checkout failed"},
                status_code=resp.status_code
            )
            if resp.status_code == 200:
                print(f"     ✓ Checkout successful: {resp.json().get('order_id')}")
        except Exception as e:
            print(f"     Warning: {e}")
        
        # Step 9: View order history
        print("  9. Viewing order history...")
        try:
            resp = self.session.get(f"{self.base_url}/orders/user123")
            self.record_request(
                "GET", f"{self.base_url}/orders/user123",
                response_data=resp.json(),
                status_code=resp.status_code
            )
        except Exception as e:
            print(f"     Warning: {e}")
        
        # Step 10: Health check
        print("  10. Health check...")
        try:
            resp = self.session.get(f"{self.base_url}/health")
            self.record_request(
                "GET", f"{self.base_url}/health",
                response_data=resp.json(),
                status_code=resp.status_code
            )
        except Exception as e:
            print(f"     Warning: {e}")
        
        print("\n✅ User session complete!")
    
    def export_har(self, output_path: str = "tests/gauntlet/flow.har"):
        """Export recorded session as HAR file."""
        har_data = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "MockClaw Gauntlet Recorder",
                    "version": "1.0.0"
                },
                "browser": {
                    "name": "MockClaw",
                    "version": "1.0.0"
                },
                "entries": self.entries
            }
        }
        
        output_file = Path(output_path)
        output_file.parent.mkdir(parents=True, exist_ok=True)
        output_file.write_text(json.dumps(har_data, indent=2), encoding='utf-8')
        
        print(f"\n📦 HAR file saved to: {output_file.absolute()}")
        print(f"   Total entries: {len(self.entries)}")
        
        return output_file


def main():
    """Main entry point."""
    
    print("=" * 60)
    print("MockClaw Gauntlet Recorder")
    print("=" * 60)
    print("\nThis script records realistic user traffic from the Dummy Shop API.")
    print("The recorded HAR file will be used for chaos testing.\n")
    
    # Check if Dummy Shop is running
    base_url = "http://localhost:9000"
    print(f"Attempting to connect to Dummy Shop at {base_url}...")
    
    try:
        resp = requests.get(f"{base_url}/health", timeout=3)
        if resp.status_code == 200:
            print("✅ Dummy Shop is running!")
        else:
            print(f"❌ Dummy Shop returned status {resp.status_code}")
            print("\nPlease start the Dummy Shop first:")
            print("  python tests/gauntlet/dummy_shop.py")
            return 1
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to Dummy Shop!")
        print("\nPlease start the Dummy Shop first:")
        print("  python tests/gauntlet/dummy_shop.py")
        print("\nThen run this script again.")
        return 1
    
    # Record session
    recorder = GauntletRecorder(base_url)
    recorder.run_user_session()
    
    # Export HAR
    har_path = recorder.export_har()
    
    print("\n" + "=" * 60)
    print("✅ Gauntlet recording complete!")
    print("=" * 60)
    print(f"\nNext steps:")
    print(f"  1. Review the HAR file: {har_path}")
    print(f"  2. Run chaos tests: python scripts/enhanced_chaos_test.py")
    
    return 0


if __name__ == "__main__":
    exit(main() or 0)
