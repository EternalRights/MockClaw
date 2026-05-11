"""
MockClaw Generator
Generates FastAPI mock endpoints from parsed HAR data.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .code_extractor import CodeExtractor
from .generation_strategy import (
    GenerationStrategy,
    LLMGenerationStrategy,
    SmartRoutingStrategy,
    TemplateGenerationStrategy,
)
from .llm_client_manager import LLMClientManager
from .prompt_builder import PromptBuilder

try:
    from importlib.metadata import version as _pkg_version
    _VERSION = _pkg_version("mockclaw")
except Exception:
    import re as _re
    _init = Path(__file__).parent.parent / "__init__.py"
    _m = _re.search(r'^__version__\s*=\s*["\']([^"\']+)', _init.read_text(encoding="utf-8"), _re.MULTILINE)
    _VERSION = _m.group(1) if _m else "0.2.0"

_INDENT = "    "

_MOCK_SERVER_HEADER_TPL = """\
# MockClaw Auto-Generated Mock Server
# Do not edit manually -- regenerate from HAR traffic.

from fastapi import FastAPI, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
from typing import Any
from starlette.middleware.base import BaseHTTPMiddleware
import time
import json
from collections import defaultdict

app = FastAPI(title='MockClaw Generated API')

# === Resilience Middleware (Auto-Injected) ===

class PathTraversalMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path.lower()
        dangerous = ['..', '%2e%2e', '%252e', '%2f%5c', '//']
        for pattern in dangerous:
            if pattern in path:
                return JSONResponse(status_code=400, content={{'error': 'Invalid path', 'code': 'PATH_TRAVERSAL_BLOCKED'}})
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
            return JSONResponse(status_code=429, content={{'error': 'Too many requests', 'code': 'RATE_LIMIT_EXCEEDED'}})
        self.request_counts[client_ip].append(current_time)
        return await call_next(request)

class GlobalErrorHandler(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            return await call_next(request)
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={{'error': str(e.detail), 'code': 'HTTP_ERROR'}})
        except Exception as e:
            return JSONResponse(status_code=500, content={{'error': 'Internal server error', 'code': 'INTERNAL_ERROR'}})

# Apply middleware
app.add_middleware(GlobalErrorHandler)
app.add_middleware(RateLimitMiddleware, requests_per_minute=60)
app.add_middleware(PathTraversalMiddleware)

@app.get("/health")
async def health():
{indent}'''Health check endpoint.'''
{indent}return {{"status": "OK", "service": "MockClaw"}}

@app.get("/mockclaw/info")
async def info():
{indent}'''MockClaw metadata endpoint.'''
{indent}return {{"generator": "MockClaw", "version": "{version}"}}

# === Generated Endpoints ===
"""


def _get_mock_server_header() -> str:
    return _MOCK_SERVER_HEADER_TPL.format(indent=_INDENT, version=_VERSION)


class GenerationResult:
    """Result of mock generation."""

    def __init__(
        self,
        success: bool,
        generated_code: str,
        endpoint_path: str,
        error: str | None = None,
    ) -> None:
        self.success = success
        self.generated_code = generated_code
        self.endpoint_path = endpoint_path
        self.error = error


class MockGenerator:
    """Generates FastAPI mock endpoints from HAR endpoint data.

    Coordinates :class:`LLMClientManager`, :class:`PromptBuilder`,
    :class:`CodeExtractor`, and a :class:`GenerationStrategy` to produce
    mock endpoint code.

    Supports two modes:
    - **LLM-assisted** -- when an OpenAI-compatible API key is configured,
      sends endpoint schemas to the model for realistic mock implementations.
    - **Fallback (template)** -- when no LLM is configured, generates stub
      endpoints directly from the HAR response data.
    - **Smart Fallback** -- when *use_smart_fallback* is ``True``, analyzes
      request bodies to generate conditional routing logic.

    Args:
        api_key: Optional API key. Falls back to LLM_API_KEY then
                 OPENAI_API_KEY env vars.
        model: Model identifier (default gpt-4o-mini, from MODEL_NAME env).
        use_smart_fallback: Enable smart routing based on request body
            analysis.
    """

    _BUILTIN_PATHS = {"/health", "/mockclaw/info"}

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        use_smart_fallback: bool = False,
    ) -> None:
        self._client_manager = LLMClientManager(api_key=api_key)
        self._prompt_builder = PromptBuilder()
        self._code_extractor = CodeExtractor()
        self.model = model or os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.use_smart_fallback = use_smart_fallback
        self._strategy = self._create_strategy()

    def _create_strategy(self) -> GenerationStrategy:
        fallback = (
            SmartRoutingStrategy()
            if self.use_smart_fallback
            else TemplateGenerationStrategy()
        )
        if self._client_manager.is_available:
            return LLMGenerationStrategy(
                client_manager=self._client_manager,
                prompt_builder=self._prompt_builder,
                code_extractor=self._code_extractor,
                model=self.model,
                fallback=fallback,
            )
        return fallback

    def generate_endpoint(
        self, endpoint_data: dict[str, Any]
    ) -> GenerationResult:
        """Generate a single mock endpoint."""
        try:
            code = self._strategy.generate(endpoint_data)
            return GenerationResult(
                success=True,
                generated_code=code,
                endpoint_path=endpoint_data["resource_path"],
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                generated_code="",
                endpoint_path=endpoint_data.get("resource_path", "unknown"),
                error=str(e),
            )

    def generate_all(
        self,
        endpoints: list[dict[str, Any]],
        output_dir: str = "generated_mocks",
        use_smart_fallback: bool | None = None,
    ) -> list[GenerationResult]:
        """Generate all mock endpoints.

        Args:
            endpoints: List of endpoint data from HAR parser
            output_dir: Directory to write generated code
            use_smart_fallback: Override instance setting for smart routing
        """
        if use_smart_fallback is not None:
            old_setting = self.use_smart_fallback
            self.use_smart_fallback = use_smart_fallback
            self._strategy = self._create_strategy()
        else:
            old_setting = None

        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results: list[GenerationResult] = []
        parts: list[str] = [_get_mock_server_header()]

        for endpoint in endpoints:
            if endpoint["resource_path"] in self._BUILTIN_PATHS:
                continue
            result = self.generate_endpoint(endpoint)
            results.append(result)
            if result.success:
                parts.append(f"# {endpoint['method']} {endpoint['resource_path']}")
                parts.append(result.generated_code)
                parts.append("")

        (output_path / "dynamic_api.py").write_text(
            "\n".join(parts), encoding="utf-8"
        )

        if old_setting is not None:
            self.use_smart_fallback = old_setting
            self._strategy = self._create_strategy()

        return results
