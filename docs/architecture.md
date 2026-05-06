# MockClaw Architecture

## Overview

MockClaw generates mock API servers from captured HTTP traffic. It transforms HAR (HTTP Archive) files into FastAPI endpoints with conditional routing based on request body analysis.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MockClaw Architecture                          │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌────────────────┐
  │   Capture    │     │     Brain      │
  │   Service    │────▶│    Service     │
  │  (Recorder)  │     │   (FastAPI)    │
  └──────────────┘     └────────────────┘
         │                     │
         │ HAR files           │ Generated
         ▼                     ▼
  ┌──────────────┐     ┌────────────────┐
  │  input_har   │     │ generated_mocks │
  │    folder    │────▶│                 │────▶ Mock Server (FastAPI)
  └──────────────┘     └────────────────┘
```

## Service Components

### Capture Service (Traffic Recorder)
- **Technology**: Python + requests
- **Purpose**: Record HTTP traffic from running APIs and export as HAR format
- **Script**: `scripts/gauntlet_recorder.py`
- **Output**: `.har` files

### Brain Service (Generator Backend)
- **Technology**: Python 3.11+ / FastAPI
- **Purpose**: Parse HAR files and generate mock API code
- **Entry**: `src/brain.py`
- **Components**:
  - `core/parser.py`: HAR file parser
  - `core/generator.py`: Template-based and LLM-assisted code generator
  - `core/route_builder.py`: FastAPI route code builder
- **Port**: 8000
- **Features**:
  - Smart Fallback routing (rule-based, no LLM required)
  - LLM-assisted generation (optional, when API key configured)
  - Automatic endpoint grouping
  - Auto-injected resilience middleware

### CLI (Command Line Interface)
- **Technology**: Python + Typer
- **Purpose**: Command-line tool for generate, serve, record, and test
- **Entry**: `src/cli.py`
- **Commands**:
  - `mockclaw generate` - Generate mock server from HAR file
  - `mockclaw serve` - Start mock API server
  - `mockclaw record` - Record traffic from running API
  - `mockclaw test` - Run chaos tests against mock server
  - `mockclaw example` - Quick start with sample data
  - `mockclaw info` - Show system information

### Dashboard (Web UI)
- **Technology**: Next.js 14 + React
- **Status**: Under development -- not yet functional
- **Port**: 3000

## Data Flow

```
1. User captures traffic → HAR file
       │
       ▼
2. Parser extracts endpoints
       │
       ▼
3. Generator creates FastAPI code (smart fallback or LLM-assisted)
       │
       ▼
4. Mock server deploys with auto-injected middleware
       │
       ▼
5. Developers use mock in testing
```

## Directory Structure

```
/MockClaw
├── src/                       # Python Backend
│   ├── core/                  # Core modules
│   │   ├── parser.py          # HAR parser
│   │   ├── generator.py       # Mock generator (strategy pattern)
│   │   ├── route_builder.py   # FastAPI route code builder
│   │   ├── generation_strategy.py  # Strategy interfaces
│   │   ├── llm_client_manager.py   # LLM client lifecycle
│   │   ├── prompt_builder.py       # LLM prompt construction
│   │   └── code_extractor.py       # LLM response parsing
│   ├── brain.py               # FastAPI backend for dashboard
│   └── cli.py                 # CLI entry point (Typer)
├── scripts/                   # Utility scripts
│   ├── enhanced_chaos_test.py # Adversarial testing
│   └── gauntlet_recorder.py   # Traffic recorder
├── web/                       # Next.js Frontend (under development)
├── tests/                     # Test suite
│   ├── gauntlet/              # Integration test data
│   ├── conftest.py            # Test configuration
│   ├── test_generation.py     # Generation tests
│   └── test_cli.py            # CLI tests
├── docs/                      # Documentation
├── setup.py                   # Package setup
└── README.md                  # Project readme
```

## Auto-Injected Middleware

Generated mock servers include built-in resilience middleware:

1. **PathTraversalMiddleware** - Blocks path traversal attacks (`../`, `%2e%2e`, etc.)
2. **RateLimitMiddleware** - In-memory rate limiting (60 req/min by default)
3. **GlobalErrorHandler** - Catches unhandled exceptions, returns JSON errors

## Smart Fallback Routing

When `--smart-fallback` is enabled, the generator analyzes request bodies
to create conditional routing logic. It automatically detects fields with
differing values across multiple requests to the same endpoint:

```python
@app.post("/checkout")
async def post_checkout(request: Request):
    body = await request.json()
    if body.get("coupon_code") == "EXPIRED2026":
        raise HTTPException(status_code=400, detail=...)
    elif body.get("coupon_code") == "SAVE10":
        return {...}
    else:
        return {...}  # default response
```

No hardcoded field names -- works with any JSON request body structure.

## Security Considerations

1. **Path Traversal Protection**: Auto-injected middleware blocks directory traversal
2. **Rate Limiting**: Prevents abuse with configurable request limits
3. **Input Validation**: All HAR files validated before processing
4. **Error Handling**: Unhandled exceptions return safe JSON responses
