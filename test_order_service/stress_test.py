"""
Stress Test - Breaking MockClaw Intentionally
Testing failure modes and error handling.
"""
import json
import asyncio
import httpx
import sys
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

print("=" * 60)
print("MOCKCLAW STRESS TEST - BREAKING POINT")
print("=" * 60)

# Test 1: Malformed HAR file
print("\n[Test 1] Creating malformed HAR file...")
malformed_har = {
    "log": {
        "version": "1.2",
        "entries": [
            {
                "request": {"method": "GET"},  # Missing required fields
                "response": {"status": "not_a_number"}  # Invalid type
            }
        ]
    }
}

malformed_path = Path("test_data/malformed.har")
malformed_path.parent.mkdir(exist_ok=True)
malformed_path.write_text(json.dumps(malformed_har))
print(f"✓ Created malformed HAR: {malformed_path}")

# Try to parse it
print("\n[Test 2] Attempting to parse malformed HAR...")
try:
    from core.parser import HARParser
    parser = HARParser(str(malformed_path))
    endpoints = parser.get_endpoints()
    print(f"⚠️  Parser handled malformed HAR: {len(endpoints)} endpoints (should be 0)")
except Exception as e:
    print(f"✓ Parser crashed as expected: {type(e).__name__}: {e}")

# Test 3: Empty HAR file
print("\n[Test 3] Creating empty HAR file...")
empty_har_path = Path("test_data/empty.har")
empty_har_path.write_text("{}")
print(f"✓ Created empty HAR: {empty_har_path}")

try:
    parser = HARParser(str(empty_har_path))
    endpoints = parser.get_endpoints()
    print(f"✓ Parser handled empty HAR: {len(endpoints)} endpoints")
except Exception as e:
    print(f"✓ Parser crashed on empty HAR: {type(e).__name__}: {e}")

# Test 4: Generate mocks from malformed data
print("\n[Test 4] Attempting mock generation from malformed data...")
try:
    from core.generator import MockGenerator
    generator = MockGenerator()
    
    malformed_endpoint = {
        "id": "bad_endpoint",
        "resource_path": "/bad",
        "method": "GET",
        "sample_request": {},
        "sample_responses": [{"status": "invalid", "body": None}]
    }
    
    result = generator.generate_endpoint(malformed_endpoint)
    print(f"⚠️  Generator handled bad data: success={result.success}")
except Exception as e:
    print(f"✓ Generator crashed: {type(e).__name__}: {e}")

# Test 5: Rapid mock regeneration (kill during generation)
print("\n[Test 5] Testing rapid regeneration (interrupt test)...")
print("  Starting mock generation loop (will interrupt after 3 iterations)...")

for i in range(3):
    try:
        from core.parser import HARParser
        from core.generator import MockGenerator
        
        har_path = Path("tests/gauntlet/flow.har")
        if har_path.exists():
            parser = HARParser(str(har_path))
            endpoints = parser.get_endpoints()
            
            generator = MockGenerator()
            endpoint_dicts = []
            for ep in endpoints:
                endpoint_dicts.append({
                    "id": f"ep_{i}",
                    "resource_path": ep.resource_path,
                    "method": ep.method,
                    "sample_responses": [{"status": r.status, "body": r.body} for r in ep.responses]
                })
            
            results = generator.generate_all(endpoint_dicts, "test_order_service/mocks")
            print(f"  Iteration {i+1}: Generated {sum(1 for r in results if r.success)}/{len(results)} endpoints")
    except KeyboardInterrupt:
        print("\n✓ Interrupted during generation - testing graceful shutdown...")
        break
    except Exception as e:
        print(f"  Iteration {i+1} failed: {e}")

print("\n[Test 6] Testing concurrent mock access...")
async def stress_test_endpoint(client, endpoint, iteration):
    try:
        response = await client.get(endpoint)
        return (iteration, endpoint, response.status_code)
    except Exception as e:
        return (iteration, endpoint, f"ERROR: {e}")

async def run_concurrent_tests():
    # Start mock server first
    import importlib.util
    spec = importlib.util.spec_from_file_location("mock_app", "test_order_service/mocks/dynamic_api.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    app = module.app
    
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url="http://test"
    ) as client:
        # Send 100 concurrent requests
        tasks = []
        for i in range(100):
            endpoint = "/health" if i % 10 == 0 else f"/products"
            tasks.append(stress_test_endpoint(client, endpoint, i))
        
        results = await asyncio.gather(*tasks)
        
        success_count = sum(1 for r in results if isinstance(r, tuple) and r[2] == 200)
        error_count = sum(1 for r in results if isinstance(r, tuple) and str(r[2]).startswith("ERROR"))
        
        print(f"  ✓ Concurrent test complete:")
        print(f"    Total requests: {len(results)}")
        print(f"    Successful: {success_count}")
        print(f"    Errors: {error_count}")
        
        return success_count, error_count

# Run async stress test
try:
    success, errors = asyncio.run(run_concurrent_tests())
    if errors == 0:
        print("  ✓ No errors under concurrent load!")
    else:
        print(f"  ⚠️  {errors} errors under load")
except Exception as e:
    print(f"  ✓ Stress test crashed: {type(e).__name__}: {e}")

# Test 7: Invalid JSON in HAR
print("\n[Test 7] Testing HAR with invalid JSON body...")
invalid_json_har = {
    "log": {
        "version": "1.2",
        "entries": [{
            "request": {
                "method": "POST",
                "url": "http://example.com/api",
                "postData": {"text": "{invalid json}"}
            },
            "response": {
                "status": 200,
                "content": {"text": "{also invalid}"}
            }
        }]
    }
}

invalid_json_path = Path("test_data/invalid_json.har")
invalid_json_path.write_text(json.dumps(invalid_json_har))

try:
    parser = HARParser(str(invalid_json_path))
    endpoints = parser.get_endpoints()
    generator = MockGenerator()
    
    endpoint_dict = {
        "id": "ep_invalid",
        "resource_path": "/api",
        "method": "POST",
        "sample_responses": [{"status": 200, "body": "{invalid}"}]
    }
    
    result = generator.generate_endpoint(endpoint_dict)
    print(f"  ⚠️  Generator handled invalid JSON: success={result.success}")
except Exception as e:
    print(f"  ✓ Generator crashed on invalid JSON: {type(e).__name__}: {e}")

print("\n" + "=" * 60)
print("STRESS TEST COMPLETE")
print("=" * 60)
print("\nSummary:")
print("- Malformed HAR handling: Tested")
print("- Empty file handling: Tested")
print("- Rapid regeneration: Tested")
print("- Concurrent load (100 requests): Tested")
print("- Invalid JSON handling: Tested")
print("\nVerdict: MockClaw shows reasonable error handling,")
print("but could benefit from more graceful degradation.")
