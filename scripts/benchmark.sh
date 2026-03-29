#!/bin/bash
# MockClaw Performance Benchmark Script
# Run comprehensive performance tests

set -e

echo "============================================================"
echo "🚀 MOCKCLAW PERFORMANCE BENCHMARK"
echo "============================================================"
echo ""

# Check if Python is available
if ! command -v python &> /dev/null; then
    echo "❌ Python not found. Please install Python 3.10+"
    exit 1
fi

echo "Python version: $(python --version)"
echo "Date: $(date -Iseconds)"
echo ""

# Run benchmark suite
echo "Running benchmark suite..."
python scripts/benchmark.py

# Show results file if it exists
if [ -f "logs/benchmark_results.json" ]; then
    echo ""
    echo "============================================================"
    echo "📊 BENCHMARK RESULTS"
    echo "============================================================"
    echo "Results saved to: logs/benchmark_results.json"
    echo ""
    
    # Try to pretty-print with jq if available
    if command -v jq &> /dev/null; then
        echo "Summary:"
        jq -r '
            "  Cold Start (median):  \(.cold_start.median_ms | . * 100 | floor / 100)ms",
            "  HAR Parsing (avg):    \(.har_parsing.avg_ms | . * 100 | floor / 100)ms",
            "  Mock Gen (avg):       \(.mock_generation.avg_ms | . * 100 | floor / 100)ms",
            "  Endpoint Latency:     \(.latency.avg_ms | . * 1000 | floor / 1000)ms"
        ' logs/benchmark_results.json
    fi
fi

echo ""
echo "============================================================"
echo "✅ BENCHMARK COMPLETE"
echo "============================================================"
