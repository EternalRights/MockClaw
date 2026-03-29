"""
MockClaw Stress Testing Suite
Tests system performance under load and edge cases.
"""

import os
import sys
import json
import time
import asyncio
import random
import string
from pathlib import Path
from typing import List, Dict, Any
from concurrent.futures import ThreadPoolExecutor

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from core.parser import HARParser
from core.generator import MockGenerator

# Test data directory
TEST_DATA_DIR = Path(__file__).parent.parent / "test_data"
TEST_DATA_DIR.mkdir(exist_ok=True)


# ==================== Test Data Generators ====================

def generate_large_har(num_requests: int = 500) -> dict:
    """
    Generate a large HAR file with many requests.
    
    Args:
        num_requests: Number of requests to generate
        
    Returns:
        HAR data structure
    """
    methods = ['GET', 'POST', 'PUT', 'DELETE', 'PATCH']
    paths = [
        '/api/users/{id}',
        '/api/products/{id}',
        '/api/orders/{id}',
        '/api/auth/login',
        '/api/auth/register',
        '/api/search',
        '/api/health',
        '/api/metrics',
    ]
    
    entries = []
    for i in range(num_requests):
        method = random.choice(methods)
        path = random.choice(paths).replace('{id}', str(random.randint(1, 10000)))
        
        entry = {
            "startedDateTime": f"2026-03-28T10:00:{i%60:02d}.000Z",
            "time": random.randint(10, 500),
            "request": {
                "method": method,
                "url": f"https://api.example.com{path}",
                "httpVersion": "HTTP/1.1",
                "headers": [
                    {"name": "Content-Type", "value": "application/json"},
                    {"name": "Authorization", "value": "Bearer token123"}
                ],
                "queryString": [
                    {"name": "page", "value": str(random.randint(1, 100))},
                    {"name": "limit", "value": str(random.randint(10, 100))}
                ],
                "postData": {
                    "mimeType": "application/json",
                    "text": json.dumps({
                        "data": ''.join(random.choices(string.ascii_letters, k=100))
                    })
                } if method in ['POST', 'PUT', 'PATCH'] else None
            },
            "response": {
                "status": random.choice([200, 201, 204, 400, 404, 500]),
                "statusText": "OK",
                "headers": [
                    {"name": "Content-Type", "value": "application/json"}
                ],
                "content": {
                    "mimeType": "application/json",
                    "text": json.dumps({
                        "id": random.randint(1, 10000),
                        "data": ''.join(random.choices(string.ascii_letters, k=200))
                    })
                }
            }
        }
        entries.append(entry)
    
    return {
        "log": {
            "version": "1.2",
            "creator": {"name": "MockClaw Stress Test", "version": "1.0"},
            "entries": entries
        }
    }


def generate_edge_case_hars() -> Dict[str, dict]:
    """
    Generate HAR files for edge case testing.
    
    Returns:
        Dictionary of test name to HAR data
    """
    return {
        "empty": {
            "log": {
                "version": "1.2",
                "creator": {"name": "Test", "version": "1.0"},
                "entries": []
            }
        },
        
        "long_url": {
            "log": {
                "version": "1.2",
                "entries": [{
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/api/resource?" + "param=value&" * 300,
                        "headers": []
                    },
                    "response": {
                        "status": 200,
                        "headers": [],
                        "content": {"mimeType": "application/json", "text": "{}"}
                    }
                }]
            }
        },
        
        "special_chars": {
            "log": {
                "version": "1.2",
                "entries": [{
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/api/test",
                        "headers": [],
                        "postData": {
                            "mimeType": "application/json",
                            "text": json.dumps({
                                "unicode": "你好世界 🎉 مرحبا",
                                "special": "<>&\"'\\n\\t\\r",
                                "emoji": "😀🎉🚀💻🔥"
                            })
                        }
                    },
                    "response": {
                        "status": 200,
                        "headers": [],
                        "content": {
                            "mimeType": "application/json",
                            "text": json.dumps({"success": True})
                        }
                    }
                }]
            }
        },
        
        "binary_data": {
            "log": {
                "version": "1.2",
                "entries": [{
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/api/upload",
                        "headers": [
                            {"name": "Content-Type", "value": "image/png"}
                        ]
                    },
                    "response": {
                        "status": 200,
                        "headers": [],
                        "content": {
                            "mimeType": "image/png",
                            "text": "iVBORw0KGgoAAAANSUhEUgAAAAEAAAAB"
                        }
                    }
                }]
            }
        },
        
        "invalid_json_response": {
            "log": {
                "version": "1.2",
                "entries": [{
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/api/broken",
                        "headers": []
                    },
                    "response": {
                        "status": 200,
                        "headers": [],
                        "content": {
                            "mimeType": "application/json",
                            "text": "{invalid json here"
                        }
                    }
                }]
            }
        }
    }


# ==================== Performance Tests ====================

def test_parse_performance():
    """Test HAR parsing performance with large files."""
    print("\n=== Parse Performance Test ===")
    
    # Generate large HAR
    print("Generating large HAR file (500 requests)...")
    large_har = generate_large_har(500)
    
    har_path = TEST_DATA_DIR / "stress_large.har"
    har_path.write_text(json.dumps(large_har), encoding='utf-8')
    
    # Measure parsing time
    print("Parsing...")
    start_time = time.time()
    
    parser = HARParser(str(har_path))
    endpoints = parser.get_endpoints()
    
    parse_time = time.time() - start_time
    
    print(f"Parsed {len(endpoints)} endpoints in {parse_time:.2f}s")
    print(f"Average: {parse_time/len(endpoints)*1000:.2f}ms per endpoint")
    
    # Assertions
    assert len(endpoints) > 0, "Should parse at least some endpoints"
    assert parse_time < 5.0, "Should parse 500 requests in under 5 seconds"
    
    # Cleanup
    har_path.unlink(missing_ok=True)
    
    return {
        "total_endpoints": len(endpoints),
        "parse_time_sec": round(parse_time, 2),
        "avg_time_per_endpoint_ms": round(parse_time/len(endpoints)*1000, 2)
    }


def test_generation_performance():
    """Test mock generation performance."""
    print("\n=== Generation Performance Test ===")
    
    # Create test endpoint
    test_endpoint = {
        "id": "test_ep",
        "resource_path": "/api/test/{id}",
        "method": "POST",
        "sample_request": {"body": json.dumps({"test": "data"})},
        "sample_response": {"body": json.dumps({"result": "ok"})}
    }
    
    # Measure generation time (without actual LLM call)
    print("Generating mock code...")
    start_time = time.time()
    
    generator = MockGenerator()
    result = generator.generate_endpoint(test_endpoint)
    
    gen_time = time.time() - start_time
    
    print(f"Generated in {gen_time:.3f}s")
    print(f"Code length: {len(result.generated_code)} characters")
    
    assert result.success, "Generation should succeed"
    assert len(result.generated_code) > 0, "Should generate some code"
    
    return {
        "generation_time_sec": round(gen_time, 3),
        "code_length_chars": len(result.generated_code)
    }


def test_concurrent_requests():
    """Test handling of concurrent generation requests."""
    print("\n=== Concurrent Request Test ===")
    
    num_concurrent = 10
    print(f"Simulating {num_concurrent} concurrent requests...")
    
    # Simulate async processing
    async def process_endpoint(index: int):
        await asyncio.sleep(random.uniform(0.5, 1.5))
        return {
            "id": f"ep_{index}",
            "status": "generated",
            "time": time.time()
        }
    
    async def run_concurrent():
        start_time = time.time()
        tasks = [process_endpoint(i) for i in range(num_concurrent)]
        results = await asyncio.gather(*tasks)
        total_time = time.time() - start_time
        return results, total_time
    
    results, total_time = asyncio.run(run_concurrent())
    
    print(f"Processed {len(results)} requests in {total_time:.2f}s")
    print(f"Average per request: {total_time/num_concurrent:.2f}s")
    
    assert len(results) == num_concurrent, "All requests should complete"
    assert total_time < 3.0, "Concurrent processing should be efficient"
    
    return {
        "total_requests": num_concurrent,
        "total_time_sec": round(total_time, 2),
        "successful": len(results)
    }


# ==================== Edge Case Tests ====================

def test_edge_cases():
    """Test handling of edge cases."""
    print("\n=== Edge Case Tests ===")
    
    edge_cases = generate_edge_case_hars()
    results = {}
    
    for name, har_data in edge_cases.items():
        print(f"\nTesting: {name}")
        
        har_path = TEST_DATA_DIR / f"edge_{name}.har"
        har_path.write_text(json.dumps(har_data), encoding='utf-8')
        
        try:
            parser = HARParser(str(har_path))
            endpoints = parser.get_endpoints()
            
            results[name] = {
                "status": "passed",
                "endpoints_found": len(endpoints),
                "error": None
            }
            print(f"  Parsed {len(endpoints)} endpoints")
            
        except Exception as e:
            results[name] = {
                "status": "error",
                "endpoints_found": 0,
                "error": str(e)
            }
            print(f"  Error: {e}")
        
        finally:
            har_path.unlink(missing_ok=True)
    
    # Summary
    passed = sum(1 for r in results.values() if r["status"] == "passed")
    print(f"\n{passed}/{len(results)} edge cases handled gracefully")
    
    return results


def test_memory_usage():
    """Test memory usage during large file processing."""
    print("\n=== Memory Usage Test ===")
    
    try:
        import psutil
        process = psutil.Process()
        
        # Baseline memory
        baseline_mb = process.memory_info().rss / 1024 / 1024
        print(f"Baseline memory: {baseline_mb:.1f} MB")
        
        # Process large HAR
        large_har = generate_large_har(1000)
        har_path = TEST_DATA_DIR / "memory_test.har"
        har_path.write_text(json.dumps(large_har), encoding='utf-8')
        
        parser = HARParser(str(har_path))
        endpoints = parser.get_endpoints()
        
        # Peak memory
        peak_mb = process.memory_info().rss / 1024 / 1024
        print(f"Peak memory: {peak_mb:.1f} MB")
        print(f"Memory increase: {peak_mb - baseline_mb:.1f} MB")
        
        har_path.unlink(missing_ok=True)
        
        return {
            "baseline_mb": round(baseline_mb, 1),
            "peak_mb": round(peak_mb, 1),
            "increase_mb": round(peak_mb - baseline_mb, 1)
        }
        
    except ImportError:
        print("psutil not installed, skipping memory test")
        return {"status": "skipped"}


# ==================== Main Test Runner ====================

def run_stress_tests():
    """Run all stress tests."""
    print("=" * 60)
    print("MockClaw Stress Testing Suite")
    print("=" * 60)
    
    results = {}
    
    try:
        results["parse_performance"] = test_parse_performance()
    except Exception as e:
        results["parse_performance"] = {"error": str(e)}
    
    try:
        results["generation_performance"] = test_generation_performance()
    except Exception as e:
        results["generation_performance"] = {"error": str(e)}
    
    try:
        results["concurrent_requests"] = test_concurrent_requests()
    except Exception as e:
        results["concurrent_requests"] = {"error": str(e)}
    
    try:
        results["edge_cases"] = test_edge_cases()
    except Exception as e:
        results["edge_cases"] = {"error": str(e)}
    
    try:
        results["memory_usage"] = test_memory_usage()
    except Exception as e:
        results["memory_usage"] = {"error": str(e)}
    
    # Final summary
    print("\n" + "=" * 60)
    print("Test Summary")
    print("=" * 60)
    
    for test_name, result in results.items():
        status = "PASSED" if "error" not in result else "FAILED"
        print(f"{test_name}: {status}")
    
    return results


if __name__ == "__main__":
    results = run_stress_tests()
    
    # Save results
    results_path = TEST_DATA_DIR / "stress_test_results.json"
    results_path.write_text(json.dumps(results, indent=2), encoding='utf-8')
    print(f"\nResults saved to: {results_path}")
