"""
MockClaw Performance Benchmark Suite
Measures startup time, throughput, memory, and latency.
"""

import subprocess
import sys
import time
import os
from pathlib import Path
from datetime import datetime

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))


def measure_cold_start(iterations: int = 5) -> dict:
    """
    Measure cold start time (from python main.py to "Ready").
    
    Args:
        iterations: Number of runs to average
        
    Returns:
        Dictionary with min, max, avg, median times
    """
    print(f"\n{'='*60}")
    print("BENCHMARK: Cold Start Time")
    print(f"{'='*60}")
    print(f"Running {iterations} iterations...\n")
    
    times = []
    
    for i in range(iterations):
        # Clear Python cache to simulate cold start
        for p in Path("src").rglob("__pycache__"):
            import shutil
            shutil.rmtree(p, ignore_errors=True)
        
        start = time.perf_counter()
        
        # Run minimal import test
        result = subprocess.run(
            [sys.executable, "-c", 
             "import sys; sys.path.insert(0, 'src'); "
             "from core.parser import HARParser; "
             "from core.generator import MockGenerator; "
             "print('READY')"],
            capture_output=True,
            text=True,
            timeout=30
        )
        
        elapsed = time.perf_counter() - start
        times.append(elapsed)
        
        if result.returncode == 0:
            print(f"  Run {i+1}: {elapsed*1000:.2f}ms ✓")
        else:
            print(f"  Run {i+1}: FAILED - {result.stderr[:100]}")
    
    times.sort()
    avg_time = sum(times) / len(times)
    median_time = times[len(times)//2]
    
    results = {
        "min_ms": min(times) * 1000,
        "max_ms": max(times) * 1000,
        "avg_ms": avg_time * 1000,
        "median_ms": median_time * 1000,
        "p95_ms": times[int(len(times)*0.95)] * 1000 if len(times) > 1 else times[-1] * 1000,
    }
    
    print(f"\n  Results:")
    print(f"    Min:    {results['min_ms']:.2f}ms")
    print(f"    Max:    {results['max_ms']:.2f}ms")
    print(f"    Avg:    {results['avg_ms']:.2f}ms")
    print(f"    Median: {results['median_ms']:.2f}ms")
    print(f"    P95:    {results['p95_ms']:.2f}ms")
    
    return results


def measure_har_parsing(har_path: str = "tests/gauntlet/flow.har", iterations: int = 10) -> dict:
    """
    Measure HAR parsing performance.
    
    Args:
        har_path: Path to HAR file
        iterations: Number of runs
        
    Returns:
        Dictionary with timing stats
    """
    print(f"\n{'='*60}")
    print("BENCHMARK: HAR Parsing")
    print(f"{'='*60}")
    
    from core.parser import HARParser
    
    times = []
    endpoint_counts = []
    
    for i in range(iterations):
        start = time.perf_counter()
        parser = HARParser(har_path)
        endpoints = parser.parse()
        elapsed = time.perf_counter() - start
        
        times.append(elapsed)
        endpoint_counts.append(len(endpoints))
        print(f"  Run {i+1}: {elapsed*1000:.2f}ms ({len(endpoints)} endpoints)")
    
    times.sort()
    avg_time = sum(times) / len(times)
    
    results = {
        "min_ms": min(times) * 1000,
        "max_ms": max(times) * 1000,
        "avg_ms": avg_time * 1000,
        "median_ms": times[len(times)//2] * 1000,
        "endpoints": endpoint_counts[0],
    }
    
    print(f"\n  Results:")
    print(f"    Min:    {results['min_ms']:.2f}ms")
    print(f"    Max:    {results['max_ms']:.2f}ms")
    print(f"    Avg:    {results['avg_ms']:.2f}ms")
    print(f"    Median: {results['median_ms']:.2f}ms")
    
    return results


def measure_mock_generation(endpoints_data: list, iterations: int = 10) -> dict:
    """
    Measure mock generation performance.
    
    Args:
        endpoints_data: List of endpoint dictionaries
        iterations: Number of runs
        
    Returns:
        Dictionary with timing stats
    """
    print(f"\n{'='*60}")
    print("BENCHMARK: Mock Generation (Fallback Mode)")
    print(f"{'='*60}")
    
    from core.generator import MockGenerator
    
    times = []
    success_counts = []
    
    for i in range(iterations):
        start = time.perf_counter()
        generator = MockGenerator()  # No API key = fallback mode
        results = generator.generate_all(endpoints_data, "generated_mocks")
        elapsed = time.perf_counter() - start
        
        times.append(elapsed)
        success_counts.append(sum(1 for r in results if r.success))
        print(f"  Run {i+1}: {elapsed*1000:.2f}ms ({success_counts[-1]} endpoints)")
    
    times.sort()
    avg_time = sum(times) / len(times)
    
    results = {
        "min_ms": min(times) * 1000,
        "max_ms": max(times) * 1000,
        "avg_ms": avg_time * 1000,
        "median_ms": times[len(times)//2] * 1000,
        "success_count": success_counts[0],
    }
    
    print(f"\n  Results:")
    print(f"    Min:    {results['min_ms']:.2f}ms")
    print(f"    Max:    {results['max_ms']:.2f}ms")
    print(f"    Avg:    {results['avg_ms']:.2f}ms")
    print(f"    Median: {results['median_ms']:.2f}ms")
    
    return results


def measure_memory_usage() -> dict:
    """
    Measure memory usage (RSS) at idle.
    
    Returns:
        Dictionary with memory stats
    """
    print(f"\n{'='*60}")
    print("BENCHMARK: Memory Usage (RSS)")
    print(f"{'='*60}")
    
    try:
        import psutil
        process = psutil.Process(os.getpid())
        
        # Measure before imports
        mem_before = process.memory_info().rss / 1024 / 1024  # MB
        
        # Import everything
        from core.parser import HARParser
        from core.generator import MockGenerator
        
        # Measure after imports
        mem_after = process.memory_info().rss / 1024 / 1024  # MB
        
        print(f"  Memory before imports: {mem_before:.2f} MB")
        print(f"  Memory after imports:  {mem_after:.2f} MB")
        print(f"  Import overhead:       {mem_after - mem_before:.2f} MB")
        
        return {
            "base_mb": mem_before,
            "with_imports_mb": mem_after,
            "overhead_mb": mem_after - mem_before,
        }
        
    except ImportError:
        print("  psutil not installed - skipping memory benchmark")
        print("  Install with: pip install psutil")
        return {"error": "psutil not available"}


def run_endpoint_latency_test(num_requests: int = 100) -> dict:
    """
    Test endpoint latency using ASGI transport.
    
    Args:
        num_requests: Number of requests to send
        
    Returns:
        Dictionary with latency stats
    """
    print(f"\n{'='*60}")
    print("BENCHMARK: Endpoint Latency (ASGI)")
    print(f"{'='*60}")
    
    try:
        import httpx
        import importlib.util
        
        mock_path = Path("generated_mocks/dynamic_api.py")
        if not mock_path.exists():
            print("  Generated mocks not found - run generation first")
            return {"error": "mocks not found"}
        
        # Load mock app
        spec = importlib.util.spec_from_file_location("mock_app", mock_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        app = module.app
        
        latencies = []
        
        async def run_test():
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=app),
                base_url="http://test"
            ) as client:
                for i in range(num_requests):
                    start = time.perf_counter()
                    await client.get("/health")
                    elapsed = time.perf_counter() - start
                    latencies.append(elapsed * 1000)  # ms
        
        import asyncio
        asyncio.run(run_test())
        
        latencies.sort()
        avg_latency = sum(latencies) / len(latencies)
        
        results = {
            "min_ms": min(latencies),
            "max_ms": max(latencies),
            "avg_ms": avg_latency,
            "median_ms": latencies[len(latencies)//2],
            "p95_ms": latencies[int(len(latencies)*0.95)],
            "requests": num_requests,
        }
        
        print(f"  Sent {num_requests} requests to /health")
        print(f"\n  Results:")
        print(f"    Min:    {results['min_ms']:.3f}ms")
        print(f"    Max:    {results['max_ms']:.3f}ms")
        print(f"    Avg:    {results['avg_ms']:.3f}ms")
        print(f"    Median: {results['median_ms']:.3f}ms")
        print(f"    P95:    {results['p95_ms']:.3f}ms")
        
        return results
        
    except Exception as e:
        print(f"  Error: {e}")
        return {"error": str(e)}


def save_benchmark_results(results: dict, output_path: str = "logs/benchmark_results.json"):
    """Save benchmark results to JSON file."""
    import json
    
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    
    results["timestamp"] = datetime.now().isoformat()
    
    with open(output, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n{'='*60}")
    print(f"BENCHMARK RESULTS SAVED TO: {output}")
    print(f"{'='*60}")


def main():
    """Run all benchmarks."""
    print("\n" + "="*60)
    print("🚀 MOCKCLAW PERFORMANCE BENCHMARK SUITE")
    print("="*60)
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Python: {sys.version}")
    print(f"Platform: {sys.platform}")
    
    all_results = {}
    
    # 1. Cold Start
    all_results["cold_start"] = measure_cold_start(iterations=5)
    
    # 2. HAR Parsing
    all_results["har_parsing"] = measure_har_parsing(iterations=10)
    
    # 3. Mock Generation
    from core.parser import HARParser
    parser = HARParser("tests/gauntlet/flow.har")
    endpoints = parser.get_endpoints()
    endpoints_data = [
        {
            "id": f"ep_{ep.resource_path}_{ep.method}".replace("/", "_"),
            "resource_path": ep.resource_path,
            "method": ep.method,
            "sample_request": {
                "body": ep.requests[0].body if ep.requests else None
            },
            "sample_responses": [
                {"status": r.status, "body": r.body}
                for r in ep.responses
            ],
            "sample_response": {
                "status": ep.responses[0].status if ep.responses else 200,
                "body": ep.responses[0].body if ep.responses else None
            },
        }
        for ep in endpoints
    ]
    all_results["mock_generation"] = measure_mock_generation(endpoints_data, iterations=10)
    
    # 4. Memory Usage
    all_results["memory"] = measure_memory_usage()
    
    # 5. Endpoint Latency
    all_results["latency"] = run_endpoint_latency_test(num_requests=100)
    
    # Save results
    save_benchmark_results(all_results)
    
    # Summary
    print("\n" + "="*60)
    print("📊 BENCHMARK SUMMARY")
    print("="*60)
    print(f"Cold Start (median):  {all_results['cold_start']['median_ms']:.2f}ms")
    print(f"HAR Parsing (avg):    {all_results['har_parsing']['avg_ms']:.2f}ms")
    print(f"Mock Gen (avg):       {all_results['mock_generation']['avg_ms']:.2f}ms")
    
    if "overhead_mb" in all_results["memory"]:
        print(f"Memory Overhead:        {all_results['memory']['overhead_mb']:.2f}MB")
    
    if "avg_ms" in all_results["latency"]:
        print(f"Endpoint Latency (avg): {all_results['latency']['avg_ms']:.3f}ms")
    
    print("="*60)
    print("✅ Benchmark complete!")
    print("="*60 + "\n")


if __name__ == "__main__":
    main()
