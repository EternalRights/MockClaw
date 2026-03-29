# CI/CD Integration Guide for MockClaw

## Quick Start

### Option 1: Run Tests Locally (No Docker)

```bash
# Install dependencies
pip install pytest pytest-asyncio httpx

# Generate mocks
python test_order_service/generate_mocks.py

# Run tests
python -m pytest test_order_service/test_order_scenarios.py -v --asyncio-mode=auto
```

### Option 2: Run Tests with Docker

```bash
# Build and run with docker-compose
cd test_order_service
docker-compose up --build
```

This will:
1. Build the mock server image
2. Start the mock server on port 8000
3. Wait for health check
4. Run pytest suite
5. Show results

### Option 3: GitHub Actions

The workflow is already configured in `.github/workflows/order_service_test.yml`.

Just push to main or create a PR, and tests will run automatically.

## Health Check

The mock server provides a health endpoint:

```bash
curl http://localhost:8000/health
# Expected: {"status": "OK", "service": "MockClaw"}
```

## Waiting for Mock Server Ready

In CI scripts, wait for the server to be ready:

```bash
# Simple wait loop
for i in {1..30}; do
  if curl -s http://localhost:8000/health | grep -q "OK"; then
    echo "✅ Mock server is ready"
    break
  fi
  echo "Waiting for mock server... ($i/30)"
  sleep 1
done
```

Or use the `wait-for-it.sh` script:

```bash
./wait-for-it.sh localhost:8000 --timeout=30 -- python -m pytest test_order_service/
```

## Cleanup

After tests complete:

```bash
# Docker cleanup
docker-compose down

# Or if running manually
docker stop order-service-mock order-service-tests
docker rm order-service-mock order-service-tests
```

## Troubleshooting

### Mock server won't start
- Check if port 8000 is already in use
- Verify `dynamic_api.py` was generated correctly
- Check Docker logs: `docker logs order-service-mock`

### Tests fail with connection errors
- Ensure mock server is running and healthy
- Check network connectivity in Docker
- Verify `MOCK_SERVER_URL` environment variable

### Mocks return wrong data
- This is a limitation of fallback (non-LLM) mode
- Configure `LLM_API_KEY` for intelligent mock generation
- Or manually edit `test_order_service/mocks/dynamic_api.py`

## Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `MOCK_SERVER_URL` | Mock server base URL | `http://localhost:8000` |
| `LLM_API_KEY` | OpenAI API key for better mocks | (none) |
| `MODEL_NAME` | LLM model to use | `gpt-4o-mini` |

## Example: Jenkins Pipeline

```groovy
pipeline {
    agent any
    
    stages {
        stage('Test') {
            steps {
                sh 'pip install -r src/requirements.txt'
                sh 'python test_order_service/generate_mocks.py'
                sh 'python -m pytest test_order_service/ -v --asyncio-mode=auto'
            }
        }
    }
}
```

## Example: GitLab CI

```yaml
test:
  image: python:3.11
  script:
    - pip install -r src/requirements.txt
    - python test_order_service/generate_mocks.py
    - python -m pytest test_order_service/ -v --asyncio-mode=auto
  artifacts:
    reports:
      junit: test-results.xml
```
