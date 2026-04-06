# Checklist

## Code Quality
- [ ] Generated dynamic_api.py has no SyntaxWarning on import
- [ ] All regex patterns in generated code use raw string format (r'...')
- [ ] No temporary debug files remain in project root
- [ ] Project directory is clean and professional

## Documentation
- [ ] README includes Windows PowerShell testing examples
- [ ] README includes Python requests examples
- [ ] README includes cURL examples for Linux/Mac
- [ ] All examples are complete with 3 test cases each (health, expired coupon, valid coupon)
- [ ] Examples are clearly formatted in code blocks

## CLI Robustness
- [ ] Port occupancy detected before server start attempt
- [ ] Error message displayed when port is occupied
- [ ] Error message includes actionable solutions
- [ ] Platform-specific commands provided (Windows vs Linux)
- [ ] Alternative port suggestion included (--port 8001)
- [ ] Server startup failures handled gracefully

## Testing & Verification
- [ ] SyntaxWarning fix verified by importing generated code
- [ ] Port detection tested with occupied port scenario
- [ ] Port detection tested with available port scenario
- [ ] PowerShell example validated on Windows
- [ ] Python example validated cross-platform
- [ ] Smart Fallback routing still works correctly after fixes
