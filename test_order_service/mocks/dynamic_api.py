# MockClaw Auto-Generated Mock Server
# Do not edit manually -- regenerate from HAR traffic.

from fastapi import FastAPI, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
from typing import Any
from starlette.middleware.base import BaseHTTPMiddleware
import re
import time
from collections import defaultdict

app = FastAPI(title='MockClaw Generated API')

# === Resilience Middleware (Auto-Injected) ===

class PathTraversalMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        dangerous = [r'\.\.', '%2e%2e', '%252e', '%2f%5c.\.', '//']
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
    """Mock endpoint -- 2 HAR scenarios recorded.
      [1] status 200: {"products": [{"id": "iphone15", "name": "iPhone 15 Pro", "p
      [2] status 200: {"products": [{"id": "iphone15", "name": "iPhone 15 Pro", "p
    """
    return "mock"


# POST /login
from fastapi import HTTPException, status
from typing import Any

@app.post("/login")
async def post__login():
    """Mock endpoint -- HAR status 200."""
    return "mock"


# GET /cart/user123
from fastapi import HTTPException, status
from typing import Any

@app.get("/cart/user123")
async def get__cart_user123():
    """Mock endpoint -- 2 HAR scenarios recorded.
      [1] status 200: {"items": [], "total": 0.0}
      [2] status 200: {"items": [{"product_id": "iphone15", "name": "iPhone 15 Pro
    """
    return "mock"


# POST /cart/user123
from fastapi import HTTPException, status
from typing import Any

@app.post("/cart/user123")
async def post__cart_user123():
    """Mock endpoint -- 2 HAR scenarios recorded.
      [1] status 200: {"message": "Added to cart", "cart": {"items": [{"product_id
      [2] status 200: {"message": "Added to cart", "cart": {"items": [{"product_id
    """
    return "mock"


# POST /checkout
from fastapi import HTTPException, status
from typing import Any

@app.post("/checkout")
async def post__checkout():
    """Mock endpoint -- 2 HAR scenarios recorded.
      [1] status 400: {"detail": {"error": "COUPON_EXPIRED", "message": "Coupon 'E
      [2] status 200: {"order_id": "ORD-20260329111619-6844", "status": "confirmed
    """
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,detail="mock")


# GET /orders/user123
from fastapi import HTTPException, status
from typing import Any

@app.get("/orders/user123")
async def get__orders_user123():
    """Mock endpoint -- HAR status 200."""
    return "mock"

