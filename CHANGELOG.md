# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Stress testing suite with concurrent request handling
- Health check endpoint with service status monitoring
- Auto-recovery watchdog for process monitoring

### Changed

- **Open Source Preparation (2026-03-29)**
  - Fixed SyntaxWarning in generated code (path traversal patterns)
  - Removed unused imports from CLI module
  - Enhanced .gitignore with additional sensitive file patterns
  - All public functions now have complete docstrings
  - Code style unified across all Python files

### Security

- Added `*.key`, `secrets.json`, `credentials.json` to .gitignore
- Verified no hardcoded API keys or secrets in codebase
- Confirmed all dependencies are up-to-date and secure

## [0.2.0] - 2026-03-29

### Added

- **Gauntlet Traffic Recorder** - Record realistic user sessions from live APIs
  - Complete shopping session workflow (10 steps)
  - Captures success and error scenarios (expired coupons, auth failures)
  - Exports to standard HAR format for replay
- **Chaos Engineering Suite** - Built-in adversarial testing
  - Concurrency testing (50+ parallel requests)
  - Garbage data injection (null values, XSS, SQL injection)
  - Path traversal attack simulation
  - Rate limiting stress tests
- **Auto-Injected Resilience Middleware**
  - `PathTraversalMiddleware` - Blocks `../`, `%2e%2e`, and bypass attempts
  - `RateLimitMiddleware` - 60 requests/minute per IP (DoS protection)
  - `GlobalErrorHandler` - Safe JSON error responses, no stack traces
- **CI/CD Integration**
  - Automated chaos tests on every push
  - Nightly security hardening runs
  - Auto-commit of test results and logs
- **Validation Tools**
  - HAR file validation script
  - Gauntlet workflow verification
  - Security audit automation

### Changed

- Updated README with Gauntlet workflow documentation
- Enhanced chaos test reporting with detailed metrics
- Improved mock generation to include resilience by default
- Optimized HAR parsing for large traffic files

### Fixed

- Fixed coupon validation logic in Dummy Shop API
- Corrected path traversal regex patterns for better coverage
- Resolved rate limiting false positives in concurrent tests
- Fixed middleware ordering in generated mocks

### Security

- **Critical**: Added path traversal protection to all generated mocks
- **Critical**: Implemented rate limiting to prevent DoS attacks
- **High**: Global error handler prevents information leakage
- **Medium**: Input validation for all HAR file uploads

### Performance

- Concurrency: 50 requests in 1.6s (stable under load)
- Rate Limiting: Active after 60 requests/minute threshold
- Path Traversal: <1ms overhead per request
- Memory: Stable under sustained load tests

### Testing

- All 8 unit tests passing
- All 4 chaos tests passing (Concurrency, Garbage, Path Traversal, Rate Limiting)
- Gauntlet validation: 100% endpoint coverage
- Resilience score: 95/100

## [0.1.0] - 2026-03-28

### Added

- Core HAR parser with endpoint detection and grouping
- LLM-based mock code generator supporting OpenAI, Claude, and Ollama
- FastAPI backend server (`brain.py`) with REST API
- Next.js dashboard with four main views:
  - Traffic Ingestion: HAR file upload with real-time parsing
  - Mock Factory: Endpoint management and generation
  - Docker Lab: Container monitoring and control
  - API Docs: Interactive OpenAPI documentation
- Docker Compose configuration for multi-service deployment
- Dark/light theme toggle with system preference detection
- Professional UI components using shadcn/ui
- Startup scripts for Windows and Unix systems
- Environment configuration template
- Comprehensive README and documentation

### Changed

- Improved parser to extract URL paths from full URLs
- Added UTF-8 encoding support for Windows console
- Optimized frontend bundle size with Turbopack

### Fixed

- Windows GBK encoding issues in CLI output
- IPv4 binding for localhost connections
- GitHub secret detection blocking push operations

### Security

- Removed hardcoded API tokens from git history
- Added environment variable configuration for credentials
- Implemented input validation for file uploads

## [0.0.1] - 2026-03-28

### Added

- Initial project structure
- Basic HAR parsing capability
- Simple mock code generation
