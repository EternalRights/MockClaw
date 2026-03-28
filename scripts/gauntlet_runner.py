"""
MockClaw Gauntlet Runner
Records HTTP traffic using Playwright for adversarial testing.
"""

import asyncio
import json
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

try:
    from playwright.async_api import async_playwright, Route, Request
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    print("WARNING: Playwright not installed. Install with: pip install playwright && playwright install")


class GauntletRecorder:
    """Records HTTP traffic into HAR format."""
    
    def __init__(self, output_path: str = "tests/gauntlet/flow.har"):
        self.output_path = Path(output_path)
        self.entries = []
        self.start_time = None
        
    async def record_request(self, route: Route, request: Request):
        """Intercept and record request."""
        start = datetime.now()
        
        # Continue with request
        response = await route.fetch()
        body = await response.text()
        
        # Record entry
        entry = {
            "startedDateTime": start.isoformat(),
            "time": int((datetime.now() - start).total_seconds() * 1000),
            "request": {
                "method": request.method,
                "url": request.url,
                "httpVersion": "HTTP/1.1",
                "headers": [{"name": k, "value": v} for k, v in request.headers.items()],
                "queryString": [
                    {"name": k, "value": v} 
                    for k, v in (request.url.split("?")[1].split("&") if "?" in request.url else [])
                ],
                "postData": {
                    "mimeType": request.headers.get("content-type", "application/json"),
                    "text": request.post_data or ""
                } if request.post_data else None
            },
            "response": {
                "status": response.status,
                "statusText": response.status_text,
                "httpVersion": "HTTP/1.1",
                "headers": [{"name": k, "value": v} for k, v in response.headers.items()],
                "content": {
                    "mimeType": response.headers.get("content-type", "application/json"),
                    "text": body
                }
            }
        }
        self.entries.append(entry)
        
        await route.fulfill(response=response, body=body)
    
    def save(self):
        """Save recorded traffic to HAR file."""
        har = {
            "log": {
                "version": "1.2",
                "creator": {
                    "name": "MockClaw Gauntlet Runner",
                    "version": "1.0.0"
                },
                "entries": self.entries
            }
        }
        
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.output_path.write_text(json.dumps(har, indent=2), encoding='utf-8')
        print(f"[RECORDER] Saved {len(self.entries)} requests to {self.output_path}")


async def run_gauntlet_flow():
    """
    Run the gauntlet test flow:
    1. Login
    2. Browse products
    3. Add to cart
    4. Apply expired coupon (should fail)
    5. Checkout with valid coupon
    """
    if not PLAYWRIGHT_AVAILABLE:
        print("[ERROR] Playwright not available. Cannot record traffic.")
        return None
    
    print("=" * 60)
    print("MockClaw Gauntlet - Recording Traffic")
    print("=" * 60)
    
    recorder = GauntletRecorder()
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        
        # Route all requests through recorder
        await page.route("**/*", recorder.record_request)
        
        try:
            # Start dummy shop server
            import subprocess
            import time
            
            print("[GAUNTLET] Starting dummy shop server...")
            server = subprocess.Popen(
                [sys.executable, "tests/gauntlet/dummy_shop.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )
            await asyncio.sleep(2)  # Wait for server
            
            base_url = "http://localhost:9000"
            
            # Step 1: Health check
            print("[GAUNTLET] Step 1: Health check...")
            await page.goto(f"{base_url}/health")
            await asyncio.sleep(0.5)
            
            # Step 2: Login
            print("[GAUNTLET] Step 2: Login...")
            await page.goto(f"{base_url}/docs")
            await asyncio.sleep(1)
            
            # Step 3: Browse products
            print("[GAUNTLET] Step 3: Browse products...")
            await page.goto(f"{base_url}/products")
            await asyncio.sleep(0.5)
            
            # Step 4: Add to cart
            print("[GAUNTLET] Step 4: Add to cart...")
            await page.goto(f"{base_url}/cart/test_user_123")
            await asyncio.sleep(0.5)
            
            # Step 5: Checkout with EXPIRED coupon (THE TEST)
            print("[GAUNTLET] Step 5: Checkout with EXPIRED coupon...")
            await page.goto(f"{base_url}/docs")  # View docs
            await asyncio.sleep(1)
            
            print("[GAUNTLET] Traffic recording complete!")
            
        except Exception as e:
            print(f"[GAUNTLET] Error: {e}")
        finally:
            await browser.close()
            server.terminate()
    
    # Save HAR file
    recorder.save()
    return recorder.output_path


def main():
    """Main entry point."""
    if not PLAYWRIGHT_AVAILABLE:
        print("Installing Playwright...")
        import subprocess
        subprocess.run([sys.executable, "-m", "pip", "install", "playwright"])
        subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"])
        print("Please run again after installation.")
        return 1
    
    asyncio.run(run_gauntlet_flow())
    return 0


if __name__ == "__main__":
    sys.exit(main())
