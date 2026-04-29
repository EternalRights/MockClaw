# MockClaw

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

Turn HAR traffic files into working mock API servers. No manual configuration needed.

## How It Works

1. Capture HTTP traffic (browser DevTools, proxy, or built-in recorder)
2. Feed the HAR file to MockClaw
3. Get a running FastAPI mock server with realistic responses

## Quick Start

```bash
# Install
pip install -r src/requirements.txt
pip install -e .

# Try the built-in example
mockclaw example

# Or generate from your own HAR file
mockclaw generate your_traffic.har ./mocks --smart-fallback

# Start the mock server
mockclaw serve ./mocks --port 8000

# Test it
curl http://localhost:8000/health
```

## Smart Fallback

When `--smart-fallback` is enabled, MockClaw automatically analyzes request bodies to generate conditional routing:

```python
# If your HAR has these requests to the same endpoint:
# POST /checkout {"role": "admin", "data": "..."} -> 200
# POST /checkout {"role": "user", "data": "..."} -> 200
# POST /checkout {"role": "guest", "data": "..."} -> 403

# MockClaw auto-detects "role" as the differing field and generates:
@app.post("/checkout")
async def post__checkout(request: Request):
    body = await request.json()
    if body.get("role") == "admin":
        return {"status": "ok", "data": {...}}
    elif body.get("role") == "user":
        return {"status": "ok", "data": {...}}
    elif body.get("role") == "guest":
        raise HTTPException(status_code=403, detail=...)
    else:
        return {"status": "ok", "data": {...}}
```

No hardcoded field names. Works with any JSON request body -- coupon codes, user roles, action types, or anything else.

## Features

- **Auto conditional routing** -- analyzes request bodies to generate if/elif/else logic
- **No LLM required** -- works offline with zero API keys
- **Auto-injected security** -- rate limiting, path traversal protection, error handling
- **Swagger UI** -- interactive API docs at /docs
- **LLM-assisted mode** -- optional OpenAI integration for richer mocks

## CLI Commands

```bash
# Quick start with sample data
mockclaw example

# Generate from HAR file
mockclaw generate traffic.har ./mocks --smart-fallback

# Start mock server
mockclaw serve ./mocks --port 8000

# Record traffic from running API
mockclaw record --url http://localhost:9000 --output traffic.har

# Run chaos tests
mockclaw test ./mocks
```

## Testing

```bash
# Windows PowerShell
Invoke-RestMethod -Uri http://localhost:8000/health

# Python
import requests
requests.get('http://localhost:8000/health').json()

# cURL
curl http://localhost:8000/health
```

## Architecture

See [docs/architecture.md](docs/architecture.md) for technical details.

## Use Cases

**Frontend development** -- Generate mocks from backend HAR files before the real API is ready.

**Testing edge cases** -- Record real traffic with different inputs, get automatic conditional routing.

**CI/CD** -- Replace flaky external API dependencies with reliable local mocks.

## Contributing

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## License

MIT License - See [LICENSE](LICENSE) file.
