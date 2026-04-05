"""
MockClaw Resilience Middleware
Security and error handling for generated mocks.
"""

import json
import re
import time
from collections import defaultdict
from typing import Callable, Dict, Any
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
import math


class PathTraversalMiddleware(BaseHTTPMiddleware):
    """Block path traversal attacks like /../../etc/passwd"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and block path traversal attacks.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            JSONResponse with 400 status if path traversal detected,
            otherwise the response from the next handler.
        """
        path = request.url.path
        
        # Check for path traversal patterns
        dangerous_patterns = [
            r'\.\.',  # ..
            r'%2e%2e',  # URL encoded ..
            r'%252e%252e',  # Double URL encoded
            r'\.\.%2f',  # Mixed encoding
            r'%2f\.\.',  # Mixed encoding
            r'//',  # Double slash (can be used for protocol bypass)
        ]
        
        for pattern in dangerous_patterns:
            if re.search(pattern, path, re.IGNORECASE):
                return JSONResponse(
                    status_code=400,
                    content={"error": "Invalid path", "code": "PATH_TRAVERSAL_BLOCKED"}
                )
        
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Simple in-memory rate limiting"""
    
    def __init__(self, app, requests_per_minute: int = 60):
        """Initialize the rate limiting middleware.

        Args:
            app: The FastAPI application instance.
            requests_per_minute: Maximum requests allowed per client IP
                per minute. Defaults to 60.
        """
        super().__init__(app)
        self.requests_per_minute = requests_per_minute
        self.request_counts: Dict[str, list] = defaultdict(list)
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and enforce rate limiting.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            JSONResponse with 429 status if rate limit exceeded,
            otherwise the response from the next handler.
        """
        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()
        
        # Clean old requests (older than 1 minute)
        self.request_counts[client_ip] = [
            t for t in self.request_counts[client_ip]
            if current_time - t < 60
        ]
        
        # Check rate limit
        if len(self.request_counts[client_ip]) >= self.requests_per_minute:
            return JSONResponse(
                status_code=429,
                content={"error": "Too many requests", "code": "RATE_LIMIT_EXCEEDED"}
            )
        
        # Record this request
        self.request_counts[client_ip].append(current_time)
        
        return await call_next(request)


class GlobalErrorHandler(BaseHTTPMiddleware):
    """Catch all errors and return proper JSON responses"""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Process the request and catch any unhandled exceptions.

        Args:
            request: The incoming HTTP request.
            call_next: The next middleware or route handler.

        Returns:
            JSONResponse with appropriate error status code and message
            if an exception occurs, otherwise the normal response.
        """
        try:
            return await call_next(request)
        except HTTPException as e:
            return JSONResponse(
                status_code=e.status_code,
                content={"error": e.detail, "code": "HTTP_ERROR"}
            )
        except Exception as e:
            # Log the error (in production, use proper logging)
            print(f"Unhandled error: {e}")
            return JSONResponse(
                status_code=500,
                content={"error": "Internal server error", "code": "INTERNAL_ERROR"}
            )


class SafeJSONEncoder(json.JSONEncoder):
    """JSON encoder that handles inf, nan, and other problematic values"""
    
    def default(self, obj: Any) -> Any:
        """Handle objects that cannot be serialized by default.

        Args:
            obj: The object to serialize.

        Returns:
            A serializable representation of the object.
        """
        return super().default(obj)
    
    def encode(self, obj: Any) -> str:
        """Encode an object to JSON, sanitizing problematic values.

        Args:
            obj: The object to encode.

        Returns:
            JSON string representation of the sanitized object.
        """
        obj = self._sanitize(obj)
        return super().encode(obj)
    
    def _sanitize(self, obj: Any) -> Any:
        """Recursively sanitize problematic values like inf and nan.

        Args:
            obj: The object to sanitize.

        Returns:
            Sanitized object with inf/nan replaced by None.
        """
        if isinstance(obj, float):
            if math.isinf(obj):
                return None
            if math.isnan(obj):
                return None
        elif isinstance(obj, dict):
            return {k: self._sanitize(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._sanitize(item) for item in obj]
        return obj


def safe_json_response(data: Any) -> JSONResponse:
    """Create a JSON response with safe encoding.

    Sanitizes problematic values like inf and nan before encoding.

    Args:
        data: The data to encode as JSON.

    Returns:
        JSONResponse with sanitized content.
    """
    sanitized = SafeJSONEncoder()._sanitize(data)
    return JSONResponse(content=sanitized)


def apply_resilience_middleware(app: FastAPI, rate_limit: int = 60):
    """Apply all resilience middleware to the FastAPI app.

    Adds middleware in the correct order (last added = first executed):
    1. PathTraversalMiddleware - blocks path traversal attacks
    2. RateLimitMiddleware - enforces rate limiting
    3. GlobalErrorHandler - catches unhandled exceptions

    Args:
        app: The FastAPI application instance.
        rate_limit: Maximum requests per minute per client IP.
            Defaults to 60.

    Returns:
        The FastAPI app with middleware applied.
    """
    app.add_middleware(GlobalErrorHandler)
    app.add_middleware(RateLimitMiddleware, requests_per_minute=rate_limit)
    app.add_middleware(PathTraversalMiddleware)
    
    return app
