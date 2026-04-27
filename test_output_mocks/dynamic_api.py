# MockClaw Auto-Generated Mock Server
# Do not edit manually -- regenerate from HAR traffic.

from fastapi import FastAPI, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
from typing import Any
from starlette.middleware.base import BaseHTTPMiddleware
import re
import time
import json
from collections import defaultdict

app = FastAPI(title='MockClaw Generated API')

# === Resilience Middleware (Auto-Injected) ===

class PathTraversalMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        dangerous = [r'\.\.', r'%2e%2e', r'%252e', r'%2f%5c\.\.', r'//']
        for pattern in dangerous:
            if re.search(pattern, path, re.IGNORECASE):
                return JSONResponse(status_code=400, content={'error': 'Invalid path', 'code': 'PATH_TRAVERSAL_BLOCKED'})
        return await call_next(request)

class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, requests_per_minute: int = 60):
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts = defaultdict(list)
    async def dispatch(self, request: Request, call_next):
        client_ip = request.client.host if request.client else 'unknown'
        current_time = time.time()
        self.request_counts[client_ip] = [t for t in self.request_counts[client_ip] if current_time - t < 60]
        if len(self.request_counts[client_ip]) >= self.requests_per_minute:
            return JSONResponse(status_code=429, content={'error': 'Too many requests', 'code': 'RATE_LIMIT_EXCEEDED'})
        self.request_counts[client_ip].append(current_time)
        return await call_next(request)

class GlobalErrorHandler(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={'error': str(e.detail), 'code': 'HTTP_ERROR'})
        except Exception as e:
            return JSONResponse(status_code=500, content={'error': 'Internal server error', 'code': 'INTERNAL_ERROR'})

# Apply middleware
app.add_middleware(GlobalErrorHandler)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
app.add_middleware(PathTraversalMiddleware)

@app.get("/health")
async def health():
    '''Health check endpoint.'''
    return {"status": "OK", "service": "MockClaw"}

@app.get("/mockclaw/info")
async def info():
    '''MockClaw metadata endpoint.'''
    return {"generator": "MockClaw", "version": "0.1.0"}

# === Generated Endpoints ===

# GET /products
from fastapi import HTTPException, status
from typing import Any

@app.get("/products")
async def get__products():
    """Mock endpoint -- HAR status 200."""
    return {"products":[{"id":1,"name":"Widget","price":29.99},{"id":2,"name":"Gadget","price":49.99}]}


# POST /checkout
from fastapi import HTTPException, status
from typing import Any

@app.post("/checkout")
async def post__checkout(request: Request):
    """Smart mock endpoint with conditional routing."""
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}

    if body.get("coupon_code") == "EXPIRED2026":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"error":"Coupon expired","code":"COUPON_EXPIRED"})
    elif body.get("coupon_code") == "SAVE10":
        return {"order_id":"ORD-12345","total":71.98,"discount":10.0}
    else:
        return {"order_id":"ORD-12345","total":71.98,"discount":10.0}

