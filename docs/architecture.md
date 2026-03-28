# MockClaw Architecture

## Overview

MockClaw is an AI-powered tool that automatically generates Mock API servers from captured HTTP traffic. It transforms HAR (HTTP Archive) files into fully functional FastAPI endpoints with realistic fake data.

## System Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           MockClaw Architecture                          │
└─────────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌────────────────┐     ┌──────────────────────────┐
  │   Capture    │     │     Brain      │     │       Dashboard         │
  │   Service    │────▶│    Service     │────▶│       (Next.js)          │
  │  (mitmproxy) │     │   (FastAPI)    │     │       Port 3000          │
  └──────────────┘     └────────────────┘     └──────────────────────────┘
         │                     │                        │
         │ HAR files           │ Generated              │ Admin UI
         ▼                     ▼                        ▼
  ┌──────────────┐     ┌────────────────┐     ┌──────────────────────────┐
  │  input_har   │     │ generated_mocks │     │   Mock Server Instance    │
  │    folder    │────▶│                 │────▶│       (FastAPI)           │
  └──────────────┘     └────────────────┘     │      Port 4000            │
                                               └──────────────────────────┘
```

## Service Components

### Service A: Capture (Traffic Interceptor)
- **Technology**: mitmproxy / Playwright
- **Purpose**: Capture HTTP traffic and export as HAR format
- **Output**: `.har` files in `input_har/` directory
- **Features**:
  - Proxy-based traffic capture
  - Browser automation with Playwright
  - HAR file export

### Service B: Brain (AI Generator)
- **Technology**: Python 3.11 + FastAPI
- **Purpose**: Parse HAR files and generate mock API code using LLM
- **Components**:
  - `parser.py`: HAR file parser
  - `generator.py`: LLM-powered code generator
  - `main.py`: CLI and file watcher
- **Port**: 8000
- **Features**:
  - LLM integration (OpenAI GPT-4 / local models)
  - Automatic endpoint grouping
  - Pydantic model generation
  - Faker data generation

### Service C: Dashboard (Admin UI)
- **Technology**: Next.js 14 + React
- **Purpose**: Web interface for managing mocks
- **Port**: 3000
- **Features**:
  - Upload HAR files
  - View generated endpoints
  - Configure mock behavior
  - Test mock responses

### Service D: Mock Server
- **Technology**: Node.js + Express / Python + FastAPI
- **Purpose**: Run the generated mock API
- **Port**: 4000
- **Features**:
  - Dynamic endpoint registration
  - Response customization
  - Error simulation

## Data Flow

```
1. User captures traffic → HAR file
       │
       ▼
2. HAR file dropped in input_har/
       │
       ▼
3. Parser extracts endpoints
       │
       ▼
4. LLM generates FastAPI code
       │
       ▼
5. Mock server deploys
       │
       ▼
6. Developers use mock in testing
```

## Design Decisions

### 1. HAR as Intermediate Format
- **Why**: Industry standard, widely supported
- **Benefits**: 
  - Can capture from any HTTP client
  - Easy to debug and inspect
  - Self-contained JSON

### 2. FastAPI for Generated Code
- **Why**: Modern, type-safe, auto-documentation
- **Benefits**:
  - Automatic OpenAPI/Swagger docs
  - Pydantic validation
  - Async support

### 3. Faker for Mock Data
- **Why**: Generates realistic, localized data
- **Benefits**:
  - 80+ data providers
  - Multiple locales
  - Consistent across runs

### 4. Docker Compose for Deployment
- **Why**: Consistent environment, easy scaling
- **Benefits**:
  - Self-contained
  - Network isolation
  - Easy orchestration

## Directory Structure

```
/MockClaw
├── docker/                    # Docker configurations
│   └── Dockerfile
├── src/                       # Python Backend
│   ├── core/                  # Core modules
│   │   ├── parser.py          # HAR parser
│   │   └── generator.py       # LLM generator
│   ├── capture/               # Traffic capture
│   └── main.py                # CLI entry point
├── web/                       # Next.js Frontend
│   ├── pages/                 # App pages
│   ├── components/            # React components
│   └── public/                # Static assets
├── docs/                      # Documentation
├── tests/                     # Test suite
├── input_har/                 # HAR input folder
├── generated_mocks/           # Generated code
├── mocks/                     # Mock server files
├── docker-compose.yml         # Container orchestration
├── README.md                  # Project readme
└── .gitignore                 # Git ignore rules
```

## API Design

### Brain Service Endpoints

```
POST /parse
  - Input: HAR file
  - Output: Parsed endpoints JSON

POST /generate
  - Input: Parsed endpoints
  - Output: Generated Python code

GET /mocks
  - Output: List of generated mocks

POST /mocks/deploy
  - Input: Mock ID
  - Output: Deployment status
```

### Mock Server Endpoints (Auto-generated)

```
GET  /health
  - Returns: {"status": "OK"}

GET  /mockclaw/info
  - Returns: Generator metadata

POST /api/login
  - Body: {"username": "...", "password": "..."}
  - Returns: {"token": "...", "user": {...}}

GET  /api/users/{id}
  - Returns: {"id": ..., "name": "...", ...}
```

## Error Handling

### Query Parameter ?status=error
When a request includes `?status=error`, the mock server returns a 500 error with detailed error information:

```python
if status_param == "error":
    raise HTTPException(
        status_code=500,
        detail={"error": "...", "code": "ERR_..."}
    )
```

## Security Considerations

1. **Token Management**: GitHub tokens stored in environment variables
2. **Network Isolation**: Docker network for service communication
3. **Input Validation**: All HAR files validated before processing
4. **Rate Limiting**: LLM API calls rate-limited

## Future Enhancements

- [ ] WebSocket support for real-time traffic capture
- [ ] gRPC endpoint generation
- [ ] Multi-format export (OpenAPI, Postman, Insomnia)
- [ ] Collaborative mock editing
- [ ] Integration with API gateways
