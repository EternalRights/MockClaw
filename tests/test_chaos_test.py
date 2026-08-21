"""
Chaos test utility tests.

Covers the pure helper functions in scripts/enhanced_chaos_test.py
(percentile calculation and millisecond formatting) which are the
deterministic, testable parts of the chaos engine.
"""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from enhanced_chaos_test import _percentile, _format_ms  # noqa: E402


class TestPercentile:
    def test_empty_list_returns_zero(self):
        assert _percentile([], 50) == 0.0

    def test_single_value(self):
        assert _percentile([42.0], 99) == 42.0

    def test_p50_of_even_list(self):
        values = [10.0, 20.0, 30.0, 40.0]
        assert _percentile(values, 50) == 20.0

    def test_p100_returns_max(self):
        values = [5.0, 10.0, 15.0, 20.0, 25.0]
        assert _percentile(values, 100) == 25.0

    def test_p0_returns_min(self):
        values = [5.0, 10.0, 15.0, 20.0, 25.0]
        assert _percentile(values, 0) == 5.0

    def test_p95_of_range(self):
        values = [float(i) for i in range(1, 101)]  # 1..100
        assert _percentile(values, 95) == 95.0


class TestFormatMs:
    def test_rounds_to_two_decimals(self):
        assert _format_ms(1.23456) == 1.23

    def test_preserves_integers(self):
        assert _format_ms(5.0) == 5.0

    def test_zero(self):
        assert _format_ms(0.0) == 0.0
