# MockClaw Mock Server Docker Image
# Use this to run generated mocks in CI/CD pipelines

FROM python:3.11-slim

WORKDIR /app

# Install dependencies
RUN pip install --no-cache-dir fastapi uvicorn httpx

# Copy generated mocks
COPY test_order_service/mocks/ /app/mocks/

# Copy test file (optional)
COPY test_order_service/test_order_scenarios.py /app/
COPY test_order_service/conftest.py /app/

# Expose port
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import httpx; exit(0 if httpx.get('http://localhost:8000/health').status_code == 200 else 1)"

# Run mock server
CMD ["uvicorn", "mocks.dynamic_api:app", "--host", "0.0.0.0", "--port", "8000"]
