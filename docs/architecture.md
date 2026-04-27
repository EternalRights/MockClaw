# MockClaw Architecture

## Overview

MockClaw is an AI-powered tool that automatically generates Mock API servers from captured HTTP traffic. It transforms HAR (HTTP Archive) files into fully functional FastAPI endpoints with realistic fake data.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MockClaw Architecture                          │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌────────────────┐     ┌──────────────────────────┐
  │   Capture    │     │     Brain      │     │       Dashboard         │
  │   Service    │────▶│    Service     │────▶│       (Next.js)          │
  │  (Recorder)  │     │   (FastAPI)    │     │       Port 3000          │
  └──────────────┘     └────────────────┘     └──────────────────────────┘
         │                     │                        │
         │ HAR files           │ Generated              │ Admin UI
         ▼                     ▼                        ▼
  ┌──────────────┐     ┌────────────────┐     ┌──────────────────────────┐
  │  input_har   │     │ generated_mocks │     │   Mock Server Instance    │
  │    folder    │────▶│                 │────▶│       (FastAPI)           │
  └──────────────┘     └────────────────┘     │      Port 8000            │
                                               └──────────────────────────┘
```

## Service Components

### Service A: Capture (Traffic Recorder)
- **Technology**: Python + requests
- **Purpose**: Record HTTP traffic from running APIs and export as HAR format
- **Script**: `scripts/gauntlet_recorder.py`
- **Output**: `.har` files
- **Features**:
  - Session-based traffic recording
  - HAR file export
  - Dummy Shop integration for testing

### Service B: Brain (AI Generator Backend)
- **Technology**: Python 3.11+ / FastAPI
- **Purpose**: Parse HAR files and generate mock API code
- **Entry**: `src/brain.py`
- **Components**:
  - `core/parser.py`: HAR file parser
  - `core/generator.py`: LLM-powered and template-based code generator
- **Port**: 8000
- **Features**:
  - LLM integration (OpenAI GPT-4 / local models)
  - Smart Fallback routing (rule-based, no LLM required)
  - Automatic endpoint grouping
  - Pydantic model generation
  - Faker data generation

### Service C: CLI (Command Line Interface)
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

### Service D: Dashboard (Admin UI)
- **Technology**: Next.js 14 + React
- **Purpose**: Web interface for managing mocks
- **Port**: 3000
- **Features**:
  - Upload HAR files
  - View generated endpoints
  - Configure mock behavior
  - Test mock responses

## Data Flow

```
1. User captures traffic → HAR file
       │
       ▼
2. Parser extracts endpoints
       │
       ▼
3. Generator creates FastAPI code (LLM or template fallback)
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
│   │   ├── generator.py       # LLM + template generator
│   ├── brain.py               # FastAPI backend for dashboard
│   └── cli.py                 # CLI entry point (Typer)
├── scripts/                   # Utility scripts
│   ├── enhanced_chaos_test.py # Adversarial testing
│   └── gauntlet_recorder.py   # Traffic recorder
├── web/                       # Next.js Frontend
│   ├── app/                   # App pages
│   └── components/            # React components
├── tests/                     # Test suite
│   ├── gauntlet/              # Integration test data
│   ├── conftest.py            # Test configuration
│   ├── test_generation.py     # Generation tests
│   └── test_cli.py            # CLI tests
├── docs/                      # Documentation
├── docker-compose.yml         # Container orchestration
├── setup.py                   # Package setup
└── README.md                  # Project readme
```

## Auto-Injected Middleware

Generated mock servers include built-in resilience middleware:

1. **PathTraversalMiddleware** - Blocks path traversal attacks (../, %2e%2e, etc.)
2. **RateLimitMiddleware** - In-memory rate limiting (60 req/min by default)
3. **GlobalErrorHandler** - Catches unhandled exceptions, returns JSON errors

## Smart Fallback Routing

When `--smart-fallback` or `--no-llm` is enabled, the generator analyzes request bodies
to create conditional routing logic:

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

## Security Considerations

1. **Path Traversal Protection**: Auto-injected middleware blocks directory traversal
2. **Rate Limiting**: Prevents abuse with configurable request limits
3. **Input Validation**: All HAR files validated before processing
4. **Error Handling**: Unhandled exceptions return safe JSON responses

## Future Enhancements

- [ ] WebSocket support for real-time traffic capture
- [ ] gRPC endpoint generation
- [ ] Multi-format export (OpenAPI, Postman, Insomnia)
- [ ] Collaborative mock editing
- [ ] Integration with API gateways
