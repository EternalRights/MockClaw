# MockClaw

[![Python](https://img.shields.io/badge/Python-3.11-blue.svg)](https://python.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-1d63ed.svg)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

AI-powered HTTP traffic recorder and mock server generator.

## Features

- Automatic HAR parsing and endpoint detection
- LLM-based API specification generation
- Dockerized mock server deployment
- Interactive API documentation with OpenAPI
- Real-time traffic analysis dashboard

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
pytest tests/
```

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
