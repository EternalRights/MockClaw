# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Stress testing suite with concurrent request handling
- Health check endpoint with service status monitoring
- Auto-recovery watchdog for process monitoring

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
