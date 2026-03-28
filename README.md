# MockClaw 🥋

[![Python](https://img.shields.io/badge/Python-3.11-blue?logo=python&logoColor=white)](https://python.org)
[![Next.js](https://img.shields.io/badge/Next.js-16-black?logo=next.js)](https://nextjs.org)
[![Docker](https://img.shields.io/badge/Docker-Ready-blue?logo=docker&logoColor=white)](https://docker.com)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**Watch HTTP traffic, generate Mock APIs instantly with AI.**

![MockClaw Demo](docs/demo.png)

## ✨ Features

- 🎣 **Traffic Recording** - Capture HTTP traffic via HAR files or Curl commands
- 🧠 **AI-Powered Generation** - LLM-based mock code generation with realistic fake data
- 🐳 **Dockerized Mock Servers** - One-command deployment of generated mocks
- 📄 **Interactive API Docs** - Built-in OpenAPI documentation with "Try it out"
- 🎨 **Beautiful Dashboard** - Modern 2026-style UI with dark/light themes

## 📸 Screenshots

| Traffic Ingestion | Mock Factory |
|:---:|:---:|
| ![Traffic Tab](docs/screenshots/traffic.png) | ![Factory Tab](docs/screenshots/factory.png) |

| Docker Lab | API Docs |
|:---:|:---:|
| ![Docker Tab](docs/screenshots/docker.png) | ![Docs Tab](docs/screenshots/docs.png) |

## 🚀 Quick Start

### Prerequisites

- Python 3.11+
- Node.js 18+
- Docker (optional, for containerized mocks)

### One-Command Start

```bash
# Clone the repository
git clone https://github.com/EternalRights/MockClaw.git
cd MockClaw

# Start all services
docker-compose up -d

# Or start manually:
# Terminal 1 - Backend
cd src && pip install -r requirements.txt && python brain.py

# Terminal 2 - Frontend
cd web && npm install && npm run dev

# Open in browser
open http://localhost:3000
```

### Windows Quick Start

```batch
# Run the startup script
start.bat
```

### Linux/Mac Quick Start

```bash
# Run the startup script
chmod +x start.sh
./start.sh
```

## 🛠️ Configuration

### Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# LLM Provider: openai, claude, or ollama
LLM_PROVIDER=openai
LLM_API_KEY=sk-your-api-key
LLM_BASE_URL=https://api.openai.com/v1
MODEL_NAME=gpt-4o-mini
```

### LLM Providers

MockClaw supports multiple LLM providers:

| Provider | LLM_PROVIDER | Requirements |
|----------|--------------|--------------|
| OpenAI | `openai` | `LLM_API_KEY` |
| Anthropic Claude | `claude` | `LLM_API_KEY` |
| Ollama (Local) | `ollama` | Ollama running locally |

## 📖 How It Works

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  HAR File   │────▶│   Parser    │────▶│  Endpoints  │
└─────────────┘     └─────────────┘     └─────────────┘
                                               │
                                               ▼
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│ Mock Server │◀────│   Generator │◀────│    LLM      │
└─────────────┘     └─────────────┘     └─────────────┘
```

1. **Capture Traffic** - Export HAR from browser DevTools or use mitmproxy
2. **Parse** - Extract endpoints, methods, headers, and response schemas
3. **Generate** - AI creates FastAPI mock code with Faker data
4. **Deploy** - Run generated mocks as Docker containers

## 🎯 Use Cases

- **Frontend Development** - Mock APIs before backend is ready
- **Testing** - Generate consistent test data
- **Demos** - Create realistic API responses for presentations
- **API Design** - Prototype endpoints from specifications

## 🏗️ Architecture

```
MockClaw/
├── src/                    # Python Backend
│   ├── brain.py            # FastAPI server
│   ├── core/
│   │   ├── parser.py       # HAR parser
│   │   └── generator.py    # LLM generator
│   └── requirements.txt
├── web/                    # Next.js Frontend
│   ├── app/                # App Router pages
│   ├── components/         # React components
│   │   ├── ui/             # shadcn/ui components
│   │   └── dashboard/      # Dashboard tabs
│   └── package.json
├── docker-compose.yml      # Multi-service orchestration
└── .env.example            # Environment template
```

## 🤝 Contributing

Contributions are welcome! Please read our [Contributing Guide](CONTRIBUTING.md) for details.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'feat: Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [FastAPI](https://fastapi.tiangolo.com/) - Modern Python web framework
- [Next.js](https://nextjs.org/) - React framework for production
- [shadcn/ui](https://ui.shadcn.com/) - Beautiful UI components
- [Faker](https://faker.readthedocs.io/) - Fake data generation
- [Recharts](https://recharts.org/) - Charting library

---

<p align="center">
  Made with ❤️ by <a href="https://github.com/EternalRights">EternalRights</a>
</p>
