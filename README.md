# MockClaw Immortal Agent

[![Status](https://img.shields.io/badge/Status-IMMORTAL-red.svg)]()
[![Iterations](https://img.shields.io/badge/Iterations-3-brightgreen.svg)]()
[![Success](https://img.shields.io/badge/Success_Rate-100%25-brightgreen.svg)]()

An autonomous daemon that runs forever, generating mock APIs, testing them with chaos engineering, and self-repairing when things break.

## What is this?

This is MockClaw's "Immortal Mode" - a self-evolving system that:

1. **Janitor**: Cleans up resources between iterations
2. **Generate**: Creates mock APIs from HTTP traffic
3. **Chaos**: Tests with adversarial inputs (50 concurrent requests, garbage data, Docker kills)
4. **Repair**: Self-fixes when tests fail
5. **Polish**: Improves code quality automatically

## Quick Start

```batch
# Double-click to start the immortal loop
scripts\immortal_wrapper.bat
```

The agent will run forever (or until 1000 iterations), respawning automatically on crashes.

## Project Structure

```
D:\mockclaw-immortal\
├── scripts/
│   └── immortal_wrapper.bat    # Life support system
├── src/
│   ├── main.py                  # Immortal agent
│   └── core/
│       ├── parser.py            # HAR parser
│       ├── generator.py         # Mock generator
│       └── resilience.py        # Self-healing
├── tests/gauntlet/
│   ├── dummy_shop.py            # Test API
│   └── flow.har                 # Test traffic
├── generated_mocks/
│   └── dynamic_api.py           # Generated code
└── logs/
    ├── heartbeat.log            # Heartbeat
    └── evolution_history.md     # Evolution log
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

## The Wrapper (Life Support)

The `immortal_wrapper.bat` is your life support. If the Python agent dies, this brings it back.

```batch
@echo off
:loop
python -u src/main.py --agent-mode
timeout 5
goto loop
```

## License

MIT - Use at your own risk. This thing runs forever.

---

Built by an AI agent at 2 AM, fueled by chaos. 🥋
