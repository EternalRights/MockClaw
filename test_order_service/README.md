# Order Service Test Project

Testing MockClaw with a real e-commerce Order Service scenario.

## Requirements
- Test Create Order endpoint
- Test Apply Coupon (valid, expired, invalid)
- Test Check Order Status
- Test concurrency (5 orders at once)

## Test Scenarios
1. Happy path - order creation with valid coupon
2. Edge case - expired coupon returns 400
3. Error handling - invalid item ID
4. Concurrency - 5 orders simultaneously
