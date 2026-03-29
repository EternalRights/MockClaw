"""
Generate MockClaw mocks from HAR file for Order Service testing.
"""
import sys
import json
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.parser import HARParser
from core.generator import MockGenerator

def main():
    har_path = Path(__file__).parent.parent / "tests" / "gauntlet" / "flow.har"
    output_dir = Path(__file__).parent / "mocks"
    
    print(f"📦 Reading HAR file: {har_path}")
    if not har_path.exists():
        print(f"❌ HAR file not found: {har_path}")
        return 1
    
    print(f"📤 Output directory: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Parse HAR
    print("\n🔍 Parsing HAR file...")
    parser = HARParser(str(har_path))
    endpoints = parser.get_endpoints()
    print(f"✅ Found {len(endpoints)} endpoints")
    
    # Generate mocks
    print("\n⚙️  Generating mocks...")
    generator = MockGenerator()
    
    # Convert endpoints to dict format
    endpoint_dicts = []
    for ep in endpoints:
        all_responses = [
            {"status": r.status, "body": r.body}
            for r in ep.responses
        ]
        endpoint_dicts.append({
            "id": f"ep_{ep.resource_path}_{ep.method}".replace("/", "_").replace("{", "").replace("}", ""),
            "resource_path": ep.resource_path,
            "method": ep.method,
            "sample_request": {
                "body": ep.requests[0].body if ep.requests else None
            },
            "sample_responses": all_responses,
            "sample_response": {
                "status": ep.responses[0].status if ep.responses else 200,
                "body": ep.responses[0].body if ep.responses else None
            },
        })
    
    results = generator.generate_all(endpoint_dicts, str(output_dir))
    
    success_count = sum(1 for r in results if r.success)
    print(f"\n✅ Generated {success_count}/{len(results)} endpoints")
    
    if success_count > 0:
        print(f"\n📂 Mocks saved to: {output_dir}")
        print("\nNext steps:")
        print("  1. Check generated mocks in test_order_service/mocks/")
        print("  2. Write pytest tests")
        print("  3. Run tests against the mock server")
    
    return 0

if __name__ == "__main__":
    exit(main() or 0)
