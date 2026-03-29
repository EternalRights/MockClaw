# MockClaw

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-1d63ed.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)
[![Chaos Tests](https://img.shields.io/badge/Chaos-Engineered-red.svg)](scripts/enhanced_chaos_test.py)

AI-powered HTTP traffic recorder and mock server generator with chaos engineering.

## Features

- Automatic HAR parsing and endpoint detection
- LLM-based API specification generation
- Dockerized mock server deployment
- Interactive API documentation with OpenAPI
- Real-time traffic analysis dashboard
- **Gauntlet Traffic Recorder** - Record realistic user sessions
- **Chaos Engineering** - Built-in adversarial testing (path traversal, rate limiting, garbage data)
- **Auto-Injected Resilience** - Security middleware in all generated mocks

## Quick Start

### Prerequisites

- Python 3.11 or higher
- Node.js 18 or higher
- Docker (optional)

### Installation

```bash
# Clone repository
git clone https://github.com/EternalRights/MockClaw.git
cd MockClaw

# Install dependencies
pip install -r src/requirements.txt
cd web && npm install && cd ..

# Configure environment
cp .env.example .env
# Edit .env with your LLM API credentials
```

### Running

**Option 1: Docker Compose**

```bash
docker-compose up -d
```

**Option 2: Manual Start**

```bash
# Terminal 1 - Backend
python src/brain.py

# Terminal 2 - Frontend
cd web && npm run dev
```

**Option 3: Startup Script**

```bash
# Windows
start.bat

# Linux/Mac
./start.sh
```

Access the dashboard at http://localhost:3000

### Gauntlet Workflow (Recommended)

The Gauntlet workflow records realistic user traffic and generates hardened mocks:

```bash
# Step 1: Start the Dummy Shop API
python tests/gauntlet/dummy_shop.py

# Step 2: Record user session (creates flow.har)
python scripts/gauntlet_recorder.py

# Step 3: Generate mocks from recorded traffic
python regenerate_mocks.py

# Step 4: Run chaos tests to verify resilience
python scripts/enhanced_chaos_test.py

# Step 5: Run generated mock server
cd generated_mocks && uvicorn dynamic_api:app --host 0.0.0.0 --port 8000
```

This workflow:
1. Records a complete user shopping session (10 steps)
2. Captures both success and error scenarios (expired coupons, etc.)
3. Generates mocks with auto-injected security middleware
4. Validates resilience against adversarial attacks

## Architecture

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   HAR File   │────▶│    Parser    │────▶│  Endpoints   │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
                                                 ▼
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ Mock Server  │◀────│  Generator   │◀────│     LLM      │
└──────────────┘     └──────────────┘     └──────────────┘
```

**Components:**

- **Parser** (`src/core/parser.py`) - Extracts HTTP endpoints from HAR files
- **Generator** (`src/core/generator.py`) - Creates FastAPI mock code using LLM
- **Brain** (`src/brain.py`) - REST API server for frontend integration
- **Dashboard** (`web/`) - Next.js web interface

## Configuration

Set environment variables in `.env`:

```
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-key
LLM_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini
```

Supported providers: `openai`, `claude`, `ollama`

## API Reference

### Backend Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/health` | Health check |
| GET | `/mockclaw/info` | Service metadata |
| POST | `/parse` | Parse HAR file |
| POST | `/generate` | Generate mock for endpoint |
| POST | `/generate-all` | Batch generation |
| GET | `/endpoints` | List parsed endpoints |
| GET | `/logs` | Get generation logs |

### Example Usage

```python
import requests

# Parse HAR file
with open('traffic.har', 'rb') as f:
    response = requests.post('http://localhost:8000/parse', files={'file': f})
    endpoints = response.json()['endpoints']

# Generate mock
for endpoint in endpoints:
    requests.post('http://localhost:8000/generate', 
                  json={'endpoint_id': endpoint['id']})
```

## Project Structure

```
MockClaw/
├── src/
│   ├── brain.py           # FastAPI backend server
│   ├── main.py            # CLI interface
│   ├── core/
│   │   ├── parser.py      # HAR parser
│   │   └── generator.py   # LLM generator
│   └── requirements.txt
├── web/
│   ├── app/               # Next.js app router
│   ├── components/        # React components
│   └── package.json
├── tests/                 # Test suite
├── docker-compose.yml     # Container orchestration
├── .env.example           # Environment template
└── README.md
```

## Development

### Running Tests

```bash
# Run unit tests
pytest tests/

# Run chaos tests (adversarial testing)
python scripts/enhanced_chaos_test.py

# Run full CI pipeline
scripts/ci_immortal.bat
```

### Chaos Testing

MockClaw includes built-in chaos engineering to test resilience:

**Test Suite:**
- **Concurrency Test**: 50 parallel requests
- **Garbage Data Test**: Null values, XSS attempts, SQL injection
- **Path Traversal Test**: `../`, `%2e%2e`, and other bypass attempts
- **Rate Limiting Test**: 100 rapid requests to trigger DoS protection

**Auto-Injected Middleware:**
- `PathTraversalMiddleware` - Blocks directory traversal attacks
- `RateLimitMiddleware` - 60 requests/minute per IP
- `GlobalErrorHandler` - Safe error responses, no stack traces

### Code Style

- Python: PEP 8, type hints required
- TypeScript: ESLint configuration in `web/`

### Building for Production

```bash
# Backend
pip install -r src/requirements.txt

# Frontend
cd web && npm run build
```

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Run tests
5. Submit a pull request

## License

MIT License - see [LICENSE](LICENSE) for details.

## Acknowledgments

- FastAPI - Web framework
- Next.js - Frontend framework
- shadcn/ui - UI components
- Faker - Test data generation
