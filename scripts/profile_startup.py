"""
Profile MockClaw startup performance
"""
import cProfile
import pstats
import sys
from pathlib import Path
from pstats import SortKey

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

def profile_startup():
    """Profile the startup sequence."""
    from core.parser import HARParser
    from core.generator import MockGenerator
    
    # Simulate the startup flow
    har_path = "tests/gauntlet/flow.har"
    
    if not Path(har_path).exists():
        print(f"HAR file not found: {har_path}")
        return
    
    # Parse HAR
    parser = HARParser(har_path)
    endpoints = parser.get_endpoints()
    
    print(f"Parsed {len(endpoints)} endpoints")
    
    # Generate mocks
    generator = MockGenerator()
    results = generator.generate_all(
        [
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
        ],
        "generated_mocks"
    )
    
    print(f"Generated {sum(1 for r in results if r.success)}/{len(results)} endpoints")

if __name__ == "__main__":
    print("=" * 60)
    print("PROFILING MOCKCLAW STARTUP")
    print("=" * 60)
    
    # Ensure src is in path
    sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
    
    profiler = cProfile.Profile()
    profiler.enable()
    
    profile_startup()
    
    profiler.disable()
    
    # Sort stats by cumulative time
    stats = pstats.Stats(profiler)
    stats.sort_stats(SortKey.CUMULATIVE)
    
    print("\n" + "=" * 60)
    print("TOP 20 SLOWEST FUNCTIONS (by cumulative time)")
    print("=" * 60)
    stats.print_stats(20)
    
    # Save full stats to file
    stats_file = "logs/profile_stats.txt"
    Path("logs").mkdir(exist_ok=True)
    with open(stats_file, "w", encoding="utf-8") as f:
        stats.stream = f
        stats.print_stats()
    
    print(f"\nFull profile saved to: {stats_file}")
