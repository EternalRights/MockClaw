"""MockClaw Core Module.

Provides the foundational components for the MockClaw Immortal Agent:

- :class:`~core.parser.HARParser` — Extracts API endpoints from HTTP Archive (HAR) files.
- :class:`~core.generator.MockGenerator` — Generates FastAPI mock server code from parsed endpoints.
- :mod:`~core.resilience` — Self-healing utilities including retry decorators,
  watchdog timers, and graceful exit handling.

Usage::

    from core.parser import HARParser
    from core.generator import MockGenerator
    from core.resilience import retry, Watchdog
"""
