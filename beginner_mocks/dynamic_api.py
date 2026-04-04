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
    """Mock endpoint -- 2 HAR scenarios recorded.
      [1] status 200: {"products": [{"id": "iphone15", "name": "iPhone 15 Pro", "p
      [2] status 200: {"products": [{"id": "iphone15", "name": "iPhone 15 Pro", "p
    """
    return {"products":[{"id":"iphone15","name":"iPhone 15 Pro","price":999.99,"category":"electronics"},{"id":"macbook","name":"MacBook Pro 16\"","price":2499.99,"category":"electronics"},{"id":"airpods","name":"AirPods Pro","price":249.99,"category":"electronics"},{"id":"watch","name":"Apple Watch Ultra","price":799.99,"category":"accessories"}],"total":4}


# POST /login
from fastapi import HTTPException, status
from typing import Any

@app.post("/login")
async def post__login():
    """Mock endpoint -- HAR status 200."""
    return {"token":"jwt_token_1_1775227714.765624","user":{"id":1,"username":"testuser","email":"testuser@example.com"}}


# GET /cart/user123
from fastapi import HTTPException, status
from typing import Any

@app.get("/cart/user123")
async def get__cart_user123():
    """Mock endpoint -- 2 HAR scenarios recorded.
      [1] status 200: {"items": [], "total": 0.0}
      [2] status 200: {"items": [{"product_id": "iphone15", "name": "iPhone 15 Pro
    """
    return {"items":[],"total":0.0}


# POST /cart/user123
from fastapi import HTTPException, status
from typing import Any

@app.post("/cart/user123")
async def post__cart_user123():
    """Mock endpoint -- 2 HAR scenarios recorded.
      [1] status 200: {"message": "Added to cart", "cart": {"items": [{"product_id
      [2] status 200: {"message": "Added to cart", "cart": {"items": [{"product_id
    """
    return {"message":"Added to cart","cart":{"items":[{"product_id":"iphone15","name":"iPhone 15 Pro","price":999.99,"quantity":1}],"total":999.99}}


# POST /checkout
from fastapi import HTTPException, status
from typing import Any

@app.post("/checkout")
async def post__checkout(request: Request):
    """Smart mock endpoint with conditional routing."""
    body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {}

    if body.get("coupon_code") == "EXPIRED2026":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"detail":{"error":"COUPON_EXPIRED","message":"Coupon 'EXPIRED2026' has expired","valid_coupons":["SAVE10","SUMMER2026"]}})
    elif body.get("coupon_code") == "SAVE10":
        return {"order_id":"ORD-20260403224834-9727","status":"confirmed","items":[{"product_id":"iphone15","name":"iPhone 15 Pro","price":999.99,"quantity":1},{"product_id":"airpods","name":"AirPods Pro","price":249.99,"quantity":2}],"subtotal":1499.97,"discount":149.997,"total":1349.973,"estimated_delivery":"2026-04-05","tracking_url":"https://tracking.example.com/ORD-20260403224834-9727"}
    else:
        return {"order_id":"ORD-20260403224834-9727","status":"confirmed","items":[{"product_id":"iphone15","name":"iPhone 15 Pro","price":999.99,"quantity":1},{"product_id":"airpods","name":"AirPods Pro","price":249.99,"quantity":2}],"subtotal":1499.97,"discount":149.997,"total":1349.973,"estimated_delivery":"2026-04-05","tracking_url":"https://tracking.example.com/ORD-20260403224834-9727"}


# GET /orders/user123
from fastapi import HTTPException, status
from typing import Any

@app.get("/orders/user123")
async def get__orders_user123():
    """Mock endpoint -- HAR status 200."""
    return {"orders":[{"order_id":"ORD-20260328001","status":"delivered","total":999.99,"date":"2026-03-15"}]}

