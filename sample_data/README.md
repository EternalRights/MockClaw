# Sample Data for MockClaw

This directory contains pre-recorded traffic samples for quick testing.

## Quick Test (60 seconds)

```bash
# 1. Generate mocks from sample
mockclaw generate sample_data/flow.har ./my_mocks --no-llm

# 2. Start mock server
mockclaw serve ./my_mocks --port 8000

# 3. Run demo tests
pytest sample_data/test_demo.py -v
```

## What's Included

### flow.har
Pre-recorded user session with:
- ✅ User login
- ✅ Browse products (with category filter)
- ✅ Cart operations (add, view)
- ✅ Checkout with **expired coupon** (returns 400)
- ✅ Checkout with **valid coupon** (returns 200)
- ✅ Order history

**Total endpoints:** 7 unique paths  
**Total requests:** 11 recorded entries

### test_demo.py
Demo test file showing:
- Health check test
- Products endpoint test
- **Critical:** Expired coupon rejection test

## Recording Your Own Traffic

To record new traffic:

```bash
# Start your API server
python your_api.py

# Record traffic
mockclaw record --output my_traffic.har --url http://localhost:8000
```

## File Format

All HAR files follow the [HAR 1.2 specification](http://www.softwareishard.com/blog/har-12-spec/).

---

**Need more samples?** Open an issue at https://github.com/EternalRights/MockClaw/issues
