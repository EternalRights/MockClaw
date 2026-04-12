"""
MockClaw Self-Healing Test Suite
Validates the generator and auto-commits on success.
"""

import os
import sys
import json
import subprocess
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.parser import HARParser
from core.generator import MockGenerator


def log(msg):
    """Print without Unicode issues on Windows."""
    print(msg)


def test_har_parser(minimal_har_data):
    """Test 1: HAR Parser correctly extracts endpoints."""
    log("[TEST 1] HAR Parser")
    
    test_file = Path("test_data/dummy_login.har")
    test_file.parent.mkdir(exist_ok=True)
    test_file.write_text(json.dumps(minimal_har_data), encoding='utf-8')
    
    # Parse
    parser = HARParser(str(test_file))
    endpoints = parser.get_endpoints()
    
    assert len(endpoints) >= 2, f"Expected at least 2 endpoints, got {len(endpoints)}"
    
    # Check we have POST /api/login
    login_ep = next((e for e in endpoints if e.resource_path == "/api/login" and e.method == "POST"), None)
    assert login_ep is not None, "POST /api/login endpoint not found"
    
    log(f"   PASS: Parser found {len(endpoints)} endpoints")
    log(f"   PASS: POST /api/login found")
    return True


def test_generator(minimal_har_data):
    """Test 2: Generator creates valid Python code."""
    log("[TEST 2] Mock Generator")
    
    test_file = Path("test_data/dummy_login.har")
    test_file.write_text(json.dumps(minimal_har_data), encoding='utf-8')
    
    # Parse and export
    parser = HARParser(str(test_file))
    endpoints_data = parser.export_as_dict()
    
    # Generate
    generator = MockGenerator()
    results = generator.generate_all(endpoints_data['endpoints'], "generated_mocks")
    
    # Assert all succeeded
    assert len(results) >= 2, f"Expected at least 2 results, got {len(results)}"
    assert all(r.success for r in results), "Some generations failed"
    
    # Check generated file exists
    generated_file = Path("generated_mocks/dynamic_api.py")
    assert generated_file.exists(), f"Generated file not found: {generated_file}"
    
    # Read and check content
    content = generated_file.read_text(encoding='utf-8')
    
    # Critical checks
    assert '@app.post("/api/login")' in content or 'app.post("/api/login")' in content, \
        "Generated code missing @app.post('/api/login')"
    assert '/health' in content, "Generated code missing /health endpoint"
    assert '/mockclaw/info' in content, "Generated code missing /mockclaw/info endpoint"
    
    log(f"   PASS: Generated {len(results)} endpoints")
    log(f"   PASS: File created: {generated_file}")
    log(f"   PASS: Contains /health endpoint")
    log(f"   PASS: Contains /mockclaw/info endpoint")
    log(f"   PASS: Contains POST /api/login")
    return True


def test_health_endpoints():
    """Test 3: Verify required health endpoints exist."""
    log("[TEST 3] Health Endpoints Verification")
    
    generated_file = Path("generated_mocks/dynamic_api.py")
    content = generated_file.read_text(encoding='utf-8')
    
    # Check health endpoint returns "OK"
    assert '"status": "OK"' in content or "'status': 'OK'" in content, \
        "Health endpoint missing 'status: OK' response"
    
    # Check mockclaw/info has metadata
    assert 'MockClaw' in content, "Missing MockClaw branding"
    
    log("   PASS: /health returns status OK")
    log("   PASS: /mockclaw/info has metadata")
    return True


def git_commit_and_push(message: str):
    """Auto-commit generated code to GitHub."""
    log("[GIT] Auto-committing generated code...")
    
    token = os.getenv("GITHUB_TOKEN") or ""
    repo_url = f"https://x-access-token:{token}@github.com/EternalRights/MockClaw.git"
    
    try:
        # Configure git
        subprocess.run(["git", "config", "user.email", "mockclaw@example.com"], 
                       capture_output=True, check=True)
        subprocess.run(["git", "config", "user.name", "MockClaw Bot"], 
                       capture_output=True, check=True)
        
        # Add generated files
        subprocess.run(["git", "add", "."], capture_output=True, check=True)
        
        # Check if there are changes
        result = subprocess.run(["git", "status", "--porcelain"], 
                                capture_output=True, text=True)
        if not result.stdout.strip():
            log("   SKIP: No changes to commit")
            return True
        
        # Commit
        subprocess.run(["git", "commit", "-m", message], capture_output=True, check=True)
        
        # Set remote with token
        subprocess.run(["git", "remote", "set-url", "origin", repo_url], 
                       capture_output=True, check=True)
        
        # Push
        result = subprocess.run(["git", "push", "origin", "main", "--force"],
                               capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            log(f"   PASS: Committed: {message}")
            log("   PASS: Pushed to GitHub")
            return True
        else:
            log(f"   WARN: Push failed: {result.stderr}")
            return False
            
    except subprocess.TimeoutExpired:
        log("   FAIL: Git push timed out")
        return False
    except subprocess.CalledProcessError as e:
        log(f"   FAIL: Git error: {e}")
        return False


def main():
    """Run all tests."""
    log("=" * 60)
    log("MockClaw Test Suite - Self-Healing Validation")
    log("=" * 60)
    
    # Change to project root
    os.chdir(Path(__file__).parent.parent)
    
    results = []
    
    try:
        # Run tests
        results.append(("HAR Parser", test_har_parser()))
        results.append(("Mock Generator", test_generator()))
        results.append(("Health Endpoints", test_health_endpoints()))
        
        # Summary
        log("\n" + "=" * 60)
        log("TEST RESULTS")
        log("=" * 60)
        
        all_passed = all(r[1] for r in results)
        for name, passed in results:
            status = "PASS" if passed else "FAIL"
            log(f"  [{status}] {name}")
        
        log("=" * 60)
        
        if all_passed:
            log("\nAll tests passed! Auto-committing to GitHub...")
            git_commit_and_push(
                "feat: MockClaw auto-generated mock for /login endpoint"
            )
            log("\n=== MVP VALIDATION COMPLETE ===")
        else:
            log("\nTests failed. Debugging required.")
            sys.exit(1)
            
    except AssertionError as e:
        log(f"\nAssertion failed: {e}")
        sys.exit(1)
    except Exception as e:
        log(f"\nUnexpected error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
