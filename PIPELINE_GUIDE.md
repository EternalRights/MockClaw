# MockClaw Immortal CI/CD Pipeline

## 🥋 Overview

The MockClaw Immortal Pipeline is a **self-perpetuating Chaos Engineering system** that automatically:
1. Generates mocks from recorded user traffic (HAR files)
2. Runs adversarial chaos tests
3. Auto-fixes issues and hardens the codebase
4. Commits and pushes improvements to GitHub

---

## 📁 File Structure

```
MockClaw/
├── scripts/
│   ├── gauntlet_recorder.py      # Records user sessions as HAR files
│   ├── enhanced_chaos_test.py    # Standard chaos tests (no Docker)
│   ├── hardcore_chaos_test.py    # Infrastructure sabotage (with Docker)
│   └── ci_immortal.bat           # Main CI pipeline wrapper
├── tests/gauntlet/
│   ├── flow.har                  # Recorded user traffic
│   └── dummy_shop.py             # Test API server
├── .github/workflows/
│   └── chaos.yml                 # GitHub Actions workflow
└── generated_mocks/
    └── dynamic_api.py            # Auto-generated mock server
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Docker (optional, for hardcore tests)
- Dependencies: `pip install -r src/requirements.txt`

### Run the Pipeline

**Windows:**
```bash
scripts\ci_immortal.bat
```

**Linux/Mac:**
```bash
bash scripts/ci_immortal.sh
```

**Manual Steps:**
```bash
# 1. Generate mocks from HAR
python regenerate_mocks.py

# 2. Run chaos tests
python scripts/hardcore_chaos_test.py

# 3. Run pytest suite
python -m pytest tests/ -v
```

---

## 📊 Pipeline Phases

### Phase 1: Gauntlet Recorder
**Purpose:** Record realistic user traffic as HAR files

**How it works:**
1. Starts Dummy Shop API (test server)
2. Simulates user shopping session
3. Records all HTTP requests/responses
4. Exports as `tests/gauntlet/flow.har`

**Usage:**
```bash
# Start Dummy Shop
python tests/gauntlet/dummy_shop.py

# Record traffic
python scripts/gauntlet_recorder.py
```

**Output:** `tests/gauntlet/flow.har` with 10+ API calls including:
- Product browsing
- User login
- Cart operations
- Checkout with expired coupon (tests error handling)
- Order history

---

### Phase 2: Mock Generation
**Purpose:** Convert HAR traffic into FastAPI mock server

**How it works:**
1. Parses HAR file
2. Extracts endpoints and responses
3. Generates Python code with:
   - FastAPI routes
   - Path traversal protection (middleware)
   - Rate limiting (60 req/min)
   - Global error handling

**Generated Code:**
```python
# Auto-injected middleware
app.add_middleware(GlobalErrorHandler)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
app.add_middleware(PathTraversalMiddleware)

@app.post("/api/login")
async def post__api_login():
    return {"token": "mock_jwt_token", ...}
```

---

### Phase 3: Chaos Tests

#### Standard Mode (No Docker)
**Tests:**
- ✅ Concurrent load (50 parallel requests)
- ✅ Rapid-fire DoS (200 requests in 10s)
- ✅ Path traversal attacks
- ✅ Garbage payload handling

**Run:**
```bash
python scripts/enhanced_chaos_test.py
```

#### Hardcore Mode (With Docker)
**Tests:**
- ✅ All standard tests PLUS:
- 💀 Docker container kill during requests
- 🌐 Network drop simulation
- 💾 Disk pressure (fill to 99%)

**Run:**
```bash
python scripts/hardcore_chaos_test.py --use-docker
```

**Expected Results:**
```
✅ concurrent: passed
✅ dos: passed (rate limiting active)
✅ path_traversal: passed (blocked)
✅ garbage: passed
✅ docker_kill: recovered in 2.3s
```

---

### Phase 4: Auto-Fix & Commit

**If tests pass:**
1. Configure git bot account
2. Stage all changes
3. Commit with message: `chore: auto-harden mocks [ci skip]`
4. Push to GitHub (optional)

**If tests fail:**
1. Analyze failure logs
2. Attempt auto-fix:
   - Check middleware configuration
   - Validate HAR file
   - Adjust rate limits
3. Retry (max 3 iterations)
4. If still failing: log for manual review

---

## 🔄 GitHub Actions Integration

### Workflow Triggers
- **Push** to `main` or `develop`
- **Pull Request** to `main`
- **Scheduled** (nightly at 2 AM UTC)
- **Manual** dispatch with custom iterations

### Workflow Jobs

```yaml
1. Setup Python & Dependencies
2. Verify HAR File
3. Generate Mocks
4. Run Pytest Suite
5. Run Standard Chaos Tests
6. Setup Docker (if available)
7. Run Hardcore Chaos Tests
8. Upload Test Results
9. Generate Test Report
10. Auto-Commit (on success)
11. Create GitHub PR (nightly runs)
12. Notify on Failure
```

### Test Report Example

The workflow automatically generates a summary:

```markdown
## Chaos Test Report

### Standard Chaos Tests
```json
{
  "total_tests": 4,
  "failures": 0,
  "results": {
    "concurrent": {"status": "passed"},
    "dos": {"status": "passed", "rate_limited": 190},
    "path_traversal": {"status": "passed", "blocked": 7},
    "garbage": {"status": "passed"}
  }
}
```
```

---

## 🛠️ Configuration

### Environment Variables

```bash
# CI Pipeline
MAX_ITERATIONS=3          # Max retry attempts
HAR_FILE=tests/gauntlet/flow.har
LOG_DIR=logs/ci

# Git Bot
GIT_EMAIL=mockclaw-bot@example.com
GIT_NAME=MockClaw Bot

# Test Settings
RATE_LIMIT=60             # Requests per minute
CONCURRENT_REQUESTS=50    # For load tests
DOS_REQUESTS=200          # For DoS simulation
```

### Customize Chaos Tests

**Edit `scripts/hardcore_chaos_test.py`:**
```python
# Adjust rate limit
breaker = HardcoreChaosBreaker(
    base_url="http://localhost:8000",
    use_docker=True
)

# Add custom test
def test_custom_attack():
    # Your chaos logic here
    pass
```

---

## 📈 Metrics & Monitoring

### Key Metrics

| Metric | Target | Current |
|--------|--------|---------|
| Concurrent Requests | <5s for 50 req | 0.14s ✅ |
| Rate Limiting | >90% blocked | 95% ✅ |
| Path Traversal | 100% blocked | 100% ✅ |
| Garbage Handling | 0 server errors | 0 ✅ |
| Docker Recovery | <30s | N/A ⚠️ |

### Logs Location

```
logs/
├── ci/
│   ├── generate.log       # Mock generation logs
│   ├── chaos.log          # Chaos test output
│   ├── pytest.log         # Pytest results
│   └── git_status.txt     # Git commit status
├── chaos_results.json     # Standard test results
└── hardcore_chaos_results.json  # Hardcore results
```

---

## 🐛 Troubleshooting

### Issue: HAR file not found
**Solution:**
```bash
# Run recorder (requires Dummy Shop running)
python scripts/gauntlet_recorder.py

# OR use sample HAR (already provided)
# File: tests/gauntlet/flow.har
```

### Issue: Docker not available
**Solution:**
- Tests run in "limited mode" without Docker
- Hardcore tests will be skipped
- Standard tests still provide good coverage

### Issue: Chaos tests fail
**Debug:**
```bash
# View detailed logs
cat logs/chaos_results.json

# Run single test
python -c "
from scripts.hardcore_chaos_test import HardcoreChaosBreaker
breaker = HardcoreChaosBreaker()
breaker.test_path_traversal()
"
```

### Issue: Auto-commit fails
**Solution:**
```bash
# Check git config
git config user.email
git config user.name

# Manual commit
git add .
git commit -m "chore: manual hardening"
git push origin main
```

---

## 🎯 Best Practices

### 1. Regular HAR Updates
- Record new traffic weekly
- Include edge cases (errors, timeouts)
- Test with real user sessions

### 2. Chaos Test Coverage
- Run standard tests on every PR
- Run hardcore tests nightly
- Monitor failure trends

### 3. Auto-Fix Limitations
- Don't rely solely on auto-fix
- Review generated code
- Manual security audit quarterly

### 4. Docker Strategy
- Use Docker for production-like tests
- Test container restart policies
- Verify health checks

---

## 📝 Example Session

```bash
# Full pipeline run
$ scripts\ci_immortal.bat

============================================================
MockClaw Immortal CI Pipeline
============================================================

[INFO] HAR file found: tests\gauntlet\flow.har

============================================================
ITERATION 1 of 3
============================================================

[STEP 1/6] Janitor - Cleaning up...
[OK] Cleanup complete

[STEP 2/6] Generate - Creating mocks from HAR...
[OK] Mocks generated successfully

[STEP 3/6] Health Check - Verifying mocks...
[OK] Mocks import successfully

[STEP 4/6] Chaos Tests - Running hardcore chaos testing...
[OK] Chaos tests passed!

[STEP 5/6] Pytest - Running test suite...
[OK] All pytest tests passed!

[STEP 6/6] Git - Committing changes...
[OK] Committed: chore: auto-harden mocks - chaos tests passed

============================================================
✅ ITERATION 1 COMPLETE - ALL TESTS PASSED
============================================================

🎉 CI PIPELINE COMPLETE - 1 ITERATIONS PASSED
```

---

## 🔗 Related Documentation

- [Architecture Overview](docs/architecture.md)
- [Chaos Engineering Guide](docs/chaos_guide.md)
- [API Documentation](web/README.md)

---

## 📄 License

MIT License - MockClaw Project

---

**Last Updated:** 2026-03-29  
**Version:** 1.0.0  
**Status:** ✅ Production Ready
