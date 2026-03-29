# MockClaw Quick Start Guide

**Get MockClaw running in 5 minutes - guaranteed.**

This guide walks you through recording real API traffic and generating mock servers with zero configuration.

---

## Prerequisites

- **Python 3.9+** (3.11+ recommended)
- **pip** (comes with Python)
- No other dependencies required!

---

## Step 1: Install MockClaw

### Option A: Install from PyPI (Recommended)

```bash
pip install mockclaw
```

### Option B: Local Development Install

```bash
# Clone the repository
git clone https://github.com/EternalRights/MockClaw.git
cd MockClaw

# Install in editable mode
pip install -e .
```

---

## Step 2: Record API Traffic

Start the included demo shop API and record a complete user session:

```bash
# Terminal 1: Start the Dummy Shop API
python tests/gauntlet/dummy_shop.py
```

Leave this running in the background. In a **new terminal**, run the recorder:

```bash
# Terminal 2: Record user session (creates flow.har)
python -m src.cli record
```

**Note:** If you installed from PyPI, use `mockclaw record` instead.

**What gets recorded:**
- ✅ User login
- ✅ Browse products
- ✅ Add to cart
- ✅ Checkout with valid coupon
- ✅ Checkout with **expired** coupon (error case)

The recorder captures all HTTP traffic to `tests/gauntlet/flow.har`.

---

## Step 3: Generate Mock Server

Transform the recorded traffic into a fully-functional mock API:

```bash
python -m src.cli generate tests/gauntlet/flow.har ./my_mocks --no-llm
```

**Note:** If you installed from PyPI, use `mockclaw generate ...` instead.

**What happens:**
- Parses the HAR file
- Detects all API endpoints
- Generates FastAPI mock server code
- Auto-injects security middleware (path traversal protection, rate limiting)
- **No LLM API key required** - uses smart fallback routing

Output: `./my_mocks/dynamic_api.py`

---

## Step 4: Start the Mock Server

```bash
python -c "import uvicorn; uvicorn.run('my_mocks.dynamic_api:app', host='0.0.0.0', port=8000)"
```

Your mock API is now running at **http://localhost:8000**

**Features:**
- 📖 Interactive API docs: http://localhost:8000/docs
- 🏥 Health check: http://localhost:8000/health
- 🔒 Built-in security middleware
- ⚡ FastAPI performance

**Alternative:** If you have uvicorn in PATH:
```bash
uvicorn --app-dir my_mocks dynamic_api:app --host 0.0.0.0 --port 8000
```

---

## Step 5: Run Tests

Create a test file `test_demo.py` (already included in repo):

```python
import requests

BASE_URL = "http://localhost:8000"

def test_health():
    """Test the health endpoint."""
    response = requests.get(f"{BASE_URL}/health")
    assert response.status_code == 200
    assert response.json()["status"].lower() == "ok"

def test_products():
    """Test listing products."""
    response = requests.get(f"{BASE_URL}/products")
    assert response.status_code == 200
    data = response.json()
    assert "products" in data
    assert len(data["products"]) > 0

def test_checkout_with_expired_coupon():
    """Test that expired coupons are rejected."""
    payload = {
        "user_id": "testuser",
        "coupon_code": "EXPIRED2026"
    }
    response = requests.post(f"{BASE_URL}/checkout", json=payload)
    assert response.status_code == 400
    assert "COUPON_EXPIRED" in str(response.json())
```

Run the tests:

```bash
# Terminal 3: Run tests (mock server must be running)
python -m pytest test_demo.py -v
```

---

## Expected Output

### ✅ Generation Success

```
📦 Parsing HAR file: tests/gauntlet/flow.har
✅ Found 10 endpoints
🤖 Generating mocks...
   Mode: Smart Fallback (rule-based routing)

✅ Generated 10/10 endpoints

📂 Output directory: D:\MockClaw\my_mocks
   Main file: D:\MockClaw\my_mocks\dynamic_api.py
```

### ✅ Server Startup

```
🚀 Starting mock server...
   Module: my_mocks.dynamic_api
   Host: 0.0.0.0:8000
   Reload: False

📖 API docs: http://localhost:8000/docs
   Health: http://localhost:8000/health

Press Ctrl+C to stop

INFO:     Started server process [12345]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### ✅ Test Results

```
============================= test session starts =============================
platform win32 -- Python 3.11.5, pytest-8.0.0, pluggy-1.4.0
rootdir: D:\MockClaw
collected 3 items

test_demo.py::test_health PASSED                                         [ 33%]
test_demo.py::test_products PASSED                                       [ 66%]
test_demo.py::test_checkout_with_expired_coupon PASSED                   [100%]

============================== 3 passed in 0.52s ==============================
```

---

## Complete Workflow Summary

```bash
# 1. Install
pip install -e .

# 2. Record (Terminal 1: start dummy shop, Terminal 2: record)
python tests/gauntlet/dummy_shop.py
python -m src.cli record

# 3. Generate
python -m src.cli generate tests/gauntlet/flow.har ./my_mocks --no-llm

# 4. Serve
python -c "import uvicorn; uvicorn.run('my_mocks.dynamic_api:app', host='0.0.0.0', port=8000)"

# 5. Test
python -m pytest test_demo.py -v
```

**Total time: ~5 minutes** ⏱️

---

## What You Just Built

✅ **Recorded** real API traffic from a complete user session  
✅ **Generated** a production-ready mock server with 10 endpoints  
✅ **Tested** both success and error scenarios  
✅ **Secured** your mock with auto-injected middleware  

---

## Next Steps

- **Customize**: Edit `./my_mocks/dynamic_api.py` to add business logic
- **Deploy**: Use Docker or deploy to your cloud provider
- **Chaos Test**: Run `mockclaw test --hardcore` for adversarial testing
- **Dashboard**: Start the web UI with `python src/brain.py` + `cd web && npm run dev`

---

## Troubleshooting

### "Module not found: typer"
```bash
pip install -e .
```

### "Cannot connect to Dummy Shop"
Make sure `python tests/gauntlet/dummy_shop.py` is running in Terminal 1 before recording.

### "Port 8000 already in use"
```bash
python -c "import uvicorn; uvicorn.run('my_mocks.dynamic_api:app', host='0.0.0.0', port=8001)"
```

### Tests fail with connection error
Ensure the mock server is running: `python -c "import uvicorn; uvicorn.run('my_mocks.dynamic_api:app', host='0.0.0.0', port=8000)"`

---

**Need help?** Open an issue at https://github.com/EternalRights/MockClaw/issues
