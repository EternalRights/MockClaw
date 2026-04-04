# MockClaw Examples

This directory contains example HAR files for testing MockClaw.

## Sample HAR File

- `sample.har` - A complete shopping flow with:
  - Product browsing
  - User login
  - Cart management
  - Checkout with coupon validation
  - Order history

## Quick Start

```bash
# Generate mock server from sample HAR
mockclaw generate examples/sample.har ./my_mocks --smart-fallback

# Start the mock server
mockclaw serve ./my_mocks

# Test the API
curl http://localhost:8000/health
curl http://localhost:8000/products
```

## Test Scenarios

The sample HAR includes smart fallback scenarios:

1. **Expired Coupon Test**
   ```bash
   curl -X POST http://localhost:8000/checkout \
     -H "Content-Type: application/json" \
     -d '{"user_id":"test123","coupon_code":"EXPIRED2026"}'
   # Returns 400 error
   ```

2. **Valid Coupon Test**
   ```bash
   curl -X POST http://localhost:8000/checkout \
     -H "Content-Type: application/json" \
     -d '{"user_id":"test123","coupon_code":"SAVE10"}'
   # Returns success with discount
   ```
