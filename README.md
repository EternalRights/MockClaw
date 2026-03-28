# MockClaw Immortal Agent

[![Status](https://img.shields.io/badge/Status-IMMORTAL-red.svg)]()
[![Iterations](https://img.shields.io/badge/Iterations-3-brightgreen.svg)]()
[![Success](https://img.shields.io/badge/Success_Rate-100%25-brightgreen.svg)]()
[![Python](https://img.shields.io/badge/Python-3.13-blue.svg)]()
[![Ruff](https://img.shields.io/badge/Linter-Ruff-black.svg)]()

An autonomous daemon that runs forever, generating mock APIs from HAR traffic, testing them with chaos engineering, and self-repairing when things break.

## What is this?

This is MockClaw's "Immortal Mode" — a self-evolving system that cycles through five phases per iteration:

1. **Janitor** — Cleans up Docker containers, generated files, and Python caches.
2. **Generate** — Parses HAR recordings and produces a combined FastAPI mock server.
3. **Chaos** — Tests mocks with adversarial inputs (concurrent requests, garbage data, Docker kills).
4. **Repair** — Analyses failures and registers self-healing patches.
5. **Polish** — Lints with [ruff](https://docs.astral.sh/ruff/), formats code, and updates documentation.

## Architecture

```
                    ┌──────────────┐
                    │  HAR File    │
                    └──────┬───────┘
                           │
              ┌────────────▼────────────┐
              │    HARParser             │
              │  (normalise endpoints)  │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │   MockGenerator         │
              │  (LLM / fallback)       │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │  dynamic_api.py         │
              │  (FastAPI mock server)  │
              └────────────┬────────────┘
                           │
              ┌────────────▼────────────┐
              │  Chaos Testing          │
              │  (adversarial inputs)   │
              └────────────┬────────────┘
                           │
                   ┌───────┴───────┐
                   │               │
             ┌─────▼─────┐  ┌─────▼──────┐
             │  Repair    │  │  Polish    │
             │ (patches)  │  │ (ruff/docs)│
             └───────────┘  └────────────┘
```

## Quick Start

```batch
# Double-click to start the immortal loop
scripts\immortal_wrapper.bat
```

Or run directly:

```batch
python -u src\main.py --agent-mode --har tests\gauntlet\flow.har --max-iter 10
```

The agent will run forever (up to 1000 iterations), respawning automatically on crashes via the wrapper.

## Project Structure

```
D:\mockclaw-immortal\
├── scripts/
│   ├── immortal_wrapper.bat    # Life support — auto-restarts on crash
│   └── repair_daemon.py        # Watchdog-triggered self-repair pipeline
├── src/
│   ├── main.py                  # Immortal agent — orchestrates the 5-phase loop
│   └── core/
│       ├── __init__.py          # Core module documentation
│       ├── parser.py            # HAR parser — extracts & normalises API endpoints
│       ├── generator.py         # Mock generator — produces FastAPI server code
│       └── resilience.py        # Self-healing — retry, watchdog, patches, logging
├── tests/gauntlet/
│   ├── dummy_shop.py            # Target API for chaos testing
│   └── flow.har                 # Recorded HTTP traffic
├── generated_mocks/
│   └── dynamic_api.py           # Generated mock server (auto-created)
├── generate_test.py             # Issue-to-test generator
├── state.json                   # Agent state (iteration, CI status, etc.)
└── logs/
    ├── agent.log                # Main agent log
    ├── heartbeat.log            # Iteration heartbeat records
    ├── evolution_history.md     # Per-iteration evolution journal
    ├── chaos_results.log        # Chaos test outcomes
    └── night_shift.log          # Night shift schedule & results
```

## Iteration Results

```
Iteration 1: OK ✅
Iteration 2: OK ✅
Iteration 3: OK ✅

Success Rate: 100% (3/3)
```

## Critical Test Case

The Gauntlet validates that `/checkout` returns error for expired coupon:

```python
# This MUST return 400:
POST /checkout {"coupon_code": "EXPIRED2026"}
```

## Night Shift Schedule

The agent runs a 15-task night shift (02:00–09:00 CST) across four rounds:

| Round | Time | Tasks |
|-------|------|-------|
| 1 | 02:00–03:30 | Architect → Chaos → Publish → Janitor |
| 2 | 04:00–05:00 | CI Review → Fixer → Enhancer (docs/lint) |
| 3 | 05:30–06:30 | Second contribution cycle |
| 4 | 07:00–09:00 | Social, research, blog, report, final cleanup |

## The Wrapper (Life Support)

The `immortal_wrapper.bat` is your life support. If the Python agent dies, this brings it back — logging crash codes and cleaning up resources between respawns.

## License

MIT — Use at your own risk. This thing runs forever.

---

Built by an AI agent at 2 AM, fueled by chaos. 🥋
