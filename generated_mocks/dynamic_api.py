# MockClaw Auto-Generated Mock Server
# Do not edit manually -- regenerate from HAR traffic.

from fastapi import FastAPI, HTTPException, status
from typing import Any

app = FastAPI(title='MockClaw Generated API')

@app.get("/health")
async def health():
    '''Health check endpoint.'''
    return {"status": "OK", "service": "MockClaw"}

@app.get("/mockclaw/info")
async def info():
    '''MockClaw metadata endpoint.'''
    return {"generator": "MockClaw", "version": "0.1.0"}

# === Generated Endpoints ===

# POST /api/login
from fastapi import HTTPException, status
from typing import Any

@app.post("/api/login")
async def post__api_login():
    """Mock endpoint -- HAR status 200."""
    return {"token": "mock_jwt_token", "user": {"id": 1, "username": "testuser", "email": "test@example.com"}}


# GET /api/users/{id}
from fastapi import HTTPException, status
from typing import Any

@app.get("/api/users/{id}")
async def get__api_users_id():
    """Mock endpoint -- HAR status 500."""
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,detail={"error": "Database connection failed", "code": "ERR_DB_CONNECTION"})

