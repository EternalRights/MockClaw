"""
Profile MockClaw startup - focusing on actual runtime code
"""
import cProfile
import pstats
import sys
import time
from pathlib import Path
from pstats import SortKey

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

def profile_parser():
    """Profile HAR parsing."""
    from core.parser import HARParser
    
    har_path = "tests/gauntlet/flow.har"
    parser = HARParser(har_path)
    endpoints = parser.parse()
    return endpoints

def profile_generator(endpoints):
    """Profile mock generation."""
    from core.generator import MockGenerator
    
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
    return results

if __name__ == "__main__":
    print("=" * 60)
    print("DETAILED PROFILING - PARSER")
    print("=" * 60)
    
    profiler_parser = cProfile.Profile()
    profiler_parser.enable()
    start = time.time()
    endpoints = profile_parser()
    elapsed_parser = time.time() - start
    profiler_parser.disable()
    
    print(f"\nParser elapsed time: {elapsed_parser:.4f}s")
    print(f"Parsed {len(endpoints)} endpoints")
    
    stats_parser = pstats.Stats(profiler_parser)
    stats_parser.sort_stats(SortKey.CUMULATIVE)
    print("\nTop 15 Parser Functions:")
    stats_parser.print_stats(15)
    
    print("\n" + "=" * 60)
    print("DETAILED PROFILING - GENERATOR")
    print("=" * 60)
    
    profiler_gen = cProfile.Profile()
    profiler_gen.enable()
    start = time.time()
    results = profile_generator(endpoints)
    elapsed_gen = time.time() - start
    profiler_gen.disable()
    
    print(f"\nGenerator elapsed time: {elapsed_gen:.4f}s")
    print(f"Generated {sum(1 for r in results if r.success)}/{len(results)} endpoints")
    
    stats_gen = pstats.Stats(profiler_gen)
    stats_gen.sort_stats(SortKey.CUMULATIVE)
    print("\nTop 15 Generator Functions:")
    stats_gen.print_stats(15)
    
    # Save combined stats
    Path("logs").mkdir(exist_ok=True)
    with open("logs/detailed_profile.txt", "w", encoding="utf-8") as f:
        f.write("=" * 60 + "\n")
        f.write(f"PARSER TIME: {elapsed_parser:.4f}s\n")
        f.write(f"GENERATOR TIME: {elapsed_gen:.4f}s\n")
        f.write(f"TOTAL: {elapsed_parser + elapsed_gen:.4f}s\n")
        f.write("=" * 60 + "\n\n")
        
        f.write("PARSER STATS:\n")
        stats_parser.stream = f
        stats_parser.print_stats(30)
        
        f.write("\n" + "=" * 60 + "\n")
        f.write("GENERATOR STATS:\n")
        stats_gen.stream = f
        stats_gen.print_stats(30)
    
    print(f"\nDetailed profile saved to: logs/detailed_profile.txt")
