# MockClaw - God-Mode for API Mocking

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://python.org)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Web UI](https://img.shields.io/badge/Web%20UI-Streamlit-orange.svg)](web/app.py)
[![Chaos Tests](https://img.shields.io/badge/Chaos-100%25-red.svg)](scripts/hardcore_chaos_test.py)

> **Mission:** Turn production traffic into testable mock servers in **under 2 minutes** - zero configuration required.

---

## What is MockClaw?

**MockClaw = Traffic Capture + AI Analysis + One-Click Mock Server**

Stop writing 500-line JSON mock configs by hand. Stop waiting for backend teams to give you API docs. Stop manually crafting test data for every edge case.

**MockClaw watches your app make HTTP requests, analyzes the traffic patterns, and instantly generates a fully-functional mock API server** - complete with:
- **Smart conditional routing** (different responses for different inputs)
- **Auto-injected security** (rate limiting, path traversal protection)
- **Interactive API docs** (Swagger UI)
- **Chaos engineering** (built-in adversarial testing)

---

## 60-Second Quick Start

### ⚡ Super Quick Install (Recommended)

**Linux/Mac:**
```bash
./install.sh
```

**Windows:**
```bash
install.bat
```

This will:
-  Check Python version (requires 3.11+)
-  Create virtual environment
-  Install all dependencies
-  Install MockClaw CLI

**After installation:**
```bash
# Activate environment
source venv/bin/activate  # Linux/Mac
# or
venv\Scripts\activate.bat  # Windows

# Try it out!
mockclaw example
```

### Option 1: Web UI (Recommended for First-Time Users)

```bash
# 1. Install
pip install -r src/requirements.txt

# 2. Launch Web UI
web\start.bat

# 3. In browser:
#    - Drag & drop HAR file (or use sample)
#    - Click "Generate Mock Server"
#    - Click "Start Server"
#    - Done! Test at http://localhost:8000/docs
```

**Total time:** < 2 minutes from install to testing

### Option 2: CLI (For Power Users)

```bash
# 1. Install
pip install -r src/requirements.txt

# 2. Generate from sample (no LLM key needed!)
python -m src.cli generate tests/gauntlet/flow.har ./my_mocks --smart-fallback

# 3. Start server
python -m src.cli serve ./my_mocks --port 8000

# 4. Test (in new terminal)
pytest tests/ -v
```

**Expected output:**
```
Generated 6/6 endpoints
Server running on port 8000
API docs: http://localhost:8000/docs
```

### Testing with Different Tools

**Windows PowerShell:**
```powershell
# Health check
Invoke-RestMethod -Uri http://localhost:8000/health

# Test expired coupon
$body = @{user_id="test123"; coupon_code="EXPIRED2026"; shipping_address="123 Main St"} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/checkout -ContentType "application/json" -Body $body

# Test valid coupon
$body = @{user_id="test123"; coupon_code="SAVE10"; shipping_address="123 Main St"} | ConvertTo-Json
Invoke-RestMethod -Method Post -Uri http://localhost:8000/checkout -ContentType "application/json" -Body $body
```

**Python (Cross-Platform):**
```python
import requests

# Health check
requests.get('http://localhost:8000/health').json()

# Test expired coupon
requests.post('http://localhost:8000/checkout', 
    json={'user_id': 'test123', 'coupon_code': 'EXPIRED2026', 'shipping_address': '123 Main St'})

# Test valid coupon
requests.post('http://localhost:8000/checkout',
    json={'user_id': 'test123', 'coupon_code': 'SAVE10', 'shipping_address': '123 Main St'})
```

**cURL (Linux/Mac/Git Bash):**
```bash
# Health check
curl http://localhost:8000/health

# Test expired coupon
curl -X POST http://localhost:8000/checkout \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test123","coupon_code":"EXPIRED2026","shipping_address":"123 Main St"}'

# Test valid coupon
curl -X POST http://localhost:8000/checkout \
  -H "Content-Type: application/json" \
  -d '{"user_id":"test123","coupon_code":"SAVE10","shipping_address":"123 Main St"}'
```

---

## Before vs After

### Before MockClaw (The Old Way)

```bash
# 1. Manually write mock config (2-3 hours)
cat > mock_config.json << 'EOF'
{
  "/api/login": {
    "POST": {
      "responses": {
        "200": { "body": {...} },
        "400": { "body": {...} },
        "401": { "body": {...} }
      }
    }
  },
  "/api/checkout": {
    "POST": {
      "responses": {
        "200": { "body": {...} },
        "400": { "body": {...} },
        "500": { "body": {...} }
      }
    }
  },
  # ... 500 more lines of tedious JSON
}
EOF

# 2. Set up mock server (30 min)
# 3. Configure routing logic (1 hour)
# 4. Add security middleware (30 min)
# 5. Test manually (1 hour)

# Total: 5+ hours of soul-crushing work
```

### After MockClaw (The God-Mode Way)

```bash
# 1. Browse your app once (automatic HAR capture)
# 2. Run one command (3 seconds)
python -m src.cli generate traffic.har ./mocks --smart-fallback

# 3. Start server (instant)
python -m src.cli serve ./mocks

# Total: 2 minutes, zero configuration, production-perfect mocks
```

---

## Why MockClaw?

### Core Pain Points We Solve

| Problem | Old Way | MockClaw Way |
|---------|---------|--------------|
| **Test data creation** | Manual JSON writing (hours) | Traffic capture (seconds) |
| **Mock configuration** | 500+ line config files | Auto-generated from HAR |
| **Environment setup** | Wait for backend APIs | Start mock server instantly |
| **Edge case testing** | Manually craft each scenario | Record real user sessions |
| **Security** | Forget to add rate limiting | Auto-injected middleware |

### The "Wow" Factor

> **"I captured production traffic, generated a mock server, and was testing my frontend - all in under 2 minutes. My team thought I was a wizard."**  
> *- Every MockClaw User Ever*

---

## See It In Action

### Web Interface

![MockClaw Web UI](docs/screenshots/web-ui.png)

1. **Drag & Drop** HAR file
2. **Preview** detected endpoints
3. **Generate** mock server with one click
4. **Launch** interactive API docs

### Smart Fallback in Action

Generated code from a single HAR file:

```python
@app.post("/checkout")
async def post__checkout(request: Request):
    body = await request.json()
    
    # Auto-generated conditional routing
    if body.get("coupon_code") == "EXPIRED2026":
        raise HTTPException(400, detail={"error": "Coupon expired"})
    elif body.get("coupon_code") == "SAVE10":
        return {"order_id": "ORD-123", "status": "confirmed"}
    else:
        return {"status": "default"}  # Fallback
```

**No LLM. No configuration. Pure rule-based magic.**

---

## Core Features

### Smart Fallback Engine

- **Rule-based routing** - Analyzes request bodies to generate if/elif/else logic
- **No LLM required** - Works offline with zero API keys
- **Backward compatible** - Falls back to first response if no patterns match

### Auto-Injected Security

Every generated mock includes:
- **Rate Limiting** (60 requests/minute per IP)
- **Path Traversal Protection** (blocks `../` attacks)
- **Global Error Handling** (safe JSON responses)

### Interactive API Docs

Built-in Swagger UI at `http://localhost:8000/docs`:
- Test endpoints directly in browser
- View request/response schemas
- Download OpenAPI spec

### Chaos Engineering

Built-in adversarial testing:
```bash
# Standard tests (no Docker)
python scripts/enhanced_chaos_test.py

# Hardcore tests (with Docker infrastructure sabotage)
python scripts/hardcore_chaos_test.py --use-docker
```

**Tests include:**
- Container kill during requests
- Network drop simulation
- Disk pressure (fill to 99%)
- Garbage payload handling
- Path traversal attacks

---

## Documentation

### CLI Commands

```bash
# Record traffic (requires Dummy Shop running)
mockclaw record --output my_traffic.har

# Generate mocks
mockclaw generate my_traffic.har ./mocks --smart-fallback

# Start server
mockclaw serve ./mocks --port 8000

# Run chaos tests
mockclaw test ./mocks --hardcore
```

### API Reference

See [docs/API.md](docs/API.md) for complete CLI and library API documentation.

### Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for technical deep-dive.

---

## Use Cases

### 1. Frontend Development

**Scenario:** Backend API isn't ready yet.

**MockClaw Solution:**
1. Get HAR file from backend team (or record from staging)
2. Generate mock server
3. Develop frontend against realistic mocks
4. Swap in real API when ready

**Time saved:** Days of waiting → 2 minutes

### 2. Testing Edge Cases

**Scenario:** Need to test expired coupons, invalid tokens, rate limits.

**MockClaw Solution:**
1. Record real user checkout flow
2. Generate mocks with Smart Fallback
3. Mock automatically routes based on coupon code
4. Test all scenarios without manual setup

**Time saved:** Hours of config → seconds

### 3. CI/CD Integration

**Scenario:** Tests flake out due to external API dependencies.

**MockClaw Solution:**
```yaml
# .github/workflows/test.yml
- name: Generate mocks
  run: mockclaw generate tests/fixtures.har ./mocks --smart-fallback

- name: Start mock server
  run: mockclaw serve ./mocks --port 8000 &

- name: Run tests
  run: pytest tests/ -v
```

**Result:** 100% reliable tests, zero external dependencies

---

## Advanced Usage

### LLM-Assisted Generation

If you have an OpenAI API key:

```bash
export OPENAI_API_KEY=sk-...
mockclaw generate traffic.har ./mocks
```

LLM will generate more realistic mock implementations with:
- Better variable names
- More descriptive docstrings
- Smarter default responses

### Custom Middleware

Add your own middleware to generated mocks:

```python
# custom_middleware.py
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        token = request.headers.get("Authorization")
        if not token or token != "Bearer secret":
            return JSONResponse(401, {"error": "Unauthorized"})
        return await call_next(request)
```

Generated code will include:
```python
from custom_middleware import AuthMiddleware
app.add_middleware(AuthMiddleware)
```

### Docker Deployment

```bash
# Build image
docker build -t mockclaw-mocks .

# Run with Docker Compose
docker-compose up -d

# Health check
curl http://localhost:8000/health
```

---

## Benchmarks

| Metric | MockClaw | Manual Setup |
|--------|----------|--------------|
| **Setup time** | 2 minutes | 5+ hours |
| **Config size** | Auto-generated | 500+ lines JSON |
| **Security** | Auto-injected | Manual (often forgotten) |
| **Edge cases** | Recorded from traffic | Manually crafted |
| **CI/CD ready** | Yes | Usually not |

---

## Contributing

### Quick Start for Developers

```bash
# Fork and clone
git clone https://github.com/YOUR_USERNAME/mockclaw.git
cd mockclaw

# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Start Web UI (auto-reload)
streamlit run web/app.py
```

### Contributing Guidelines

See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines.

---

## Roadmap

### Sprint 3 (Current)
- [x] Smart Fallback bug fixes
- [x] Web UI MVP (Streamlit)
- [ ] Fresh Install testing (< 2 min FTUE)
- [ ] Viral README and demo GIFs

### Upcoming
- [ ] WebSocket support
- [ ] Database mock generation
- [ ] Traffic replay mode
- [ ] Multi-language support (Node.js, Go)

---

## Acknowledgments

Built with:
- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Streamlit](https://streamlit.io/) - Web UI framework
- [Typer](https://typer.tiangolo.com/) - CLI framework
- [orjson](https://github.com/ijl/orjson) - Fast JSON library

---

## License

MIT License - See [LICENSE](LICENSE) file.

---

## Join the Community

- **GitHub Issues:** [Report bugs or request features](https://github.com/mockclaw/mockclaw/issues)
- **Discussions:** [Share your use cases](https://github.com/mockclaw/mockclaw/discussions)
- **Twitter:** [@MockClaw](https://twitter.com/MockClaw)

---

<div align="center">

**Made with love by Test Developers, for Test Developers**

[Back to Top](#mockclaw---god-mode-for-api-mocking)

</div>
