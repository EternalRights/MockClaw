"""
MockClaw AI Generator
Uses LLM to generate FastAPI mock endpoints from parsed HAR data.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Use orjson for 2-5x faster JSON serialization if available
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    import json
    orjson = None
    HAS_ORJSON = False

if TYPE_CHECKING:
    from openai import OpenAI

OPENAI_AVAILABLE = False  # Will be set to True when openai is successfully imported lazily


SYSTEM_PROMPT = """You are an expert API architect. Given this HTTP request/response pair, generate a Python FastAPI endpoint.

Requirements:
1. Use Pydantic models for request/response validation
2. Use 'Faker' library to generate realistic fake data for fields like 'name', 'email', 'address', 'phone', 'id'
3. If the response contains a list, generate exactly 5 items
4. Handle path parameters (e.g., /users/{user_id}) correctly
5. Support query parameters for filtering
6. If request has a query param `?status=error`, return a 500 error with a specific error message
7. Include proper HTTP status codes and error handling

Generate ONLY the Python code with:
- Pydantic models for request/response
- FastAPI route decorators (@app.get, @app.post, etc.)
- Faker data generation
- Type hints throughout

Return ONLY the Python code in a markdown code block labeled 'python'."""


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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_STATUS_EXC = {
    400: "HTTP_400_BAD_REQUEST",
    401: "HTTP_401_UNAUTHORIZED",
    403: "HTTP_403_FORBIDDEN",
    404: "HTTP_404_NOT_FOUND",
}

_FB = "    "  # function-body indent (4 spaces)


def _body_literal(body_text: str) -> str:
    """Compact JSON string literal from raw HAR body text."""
    try:
        parsed = json.loads(body_text)
        if HAS_ORJSON:
            return orjson.dumps(parsed).decode('utf-8')
        return json.dumps(parsed, ensure_ascii=False)
    except Exception:
        return '"mock"'


def _route_from_responses(
    method: str,
    path: str,
    all_responses: list[dict[str, Any]],
    func_name: str,
) -> str:
    """Build a complete FastAPI route string for one endpoint.

    When multiple responses exist, the first (default) response is used at
    runtime and the docstring lists all observed HAR scenarios for reference.
    """
    sc0 = all_responses[0].get("status", 200)
    body0 = _body_literal(all_responses[0].get("body") or "")

    if 400 <= sc0 < 600:
        exc = _STATUS_EXC.get(sc0, "HTTP_500_INTERNAL_SERVER_ERROR")
        body_code = f"{_FB}raise HTTPException(status_code=status.{exc},detail={body0})"
    else:
        body_code = f"{_FB}return {body0}"

    if len(all_responses) > 1:
        # Docstring: list all observed HAR scenarios
        lines = [
            f'@app.{method.lower()}("{path}")',
            f"async def {func_name}():",
            f'{_FB}"""Mock endpoint -- {len(all_responses)} HAR scenarios recorded.',
        ]
        for i, resp in enumerate(all_responses, start=1):
            sc = resp.get("status", 200)
            preview = (resp.get("body") or "")[:60]
            lines.append(f'{_FB}  [{i}] status {sc}: {preview}')
        lines.append(f'{_FB}"""')
        lines.append(body_code)
        return "\n".join(lines) + "\n"

    return (
        f'@app.{method.lower()}("{path}")\n'
        f"async def {func_name}():\n"
        f'{_FB}"""Mock endpoint -- HAR status {sc0}."""\n'
        f"{body_code}\n"
    )


# ---------------------------------------------------------------------------
# MockGenerator
# ---------------------------------------------------------------------------


def _get_openai_client(api_key: str | None = None, base_url: str | None = None) -> Any:
    """
    Lazy load OpenAI client only when needed.
    
    This avoids the 800ms+ import cost when LLM is not configured.
    
    Args:
        api_key: Optional API key
        base_url: Optional base URL for API endpoint
        
    Returns:
        OpenAI client instance or None if not available/configured
    """
    global OPENAI_AVAILABLE
    
    if not hasattr(_get_openai_client, "_client_cache"):
        _get_openai_client._client_cache = None
        
        # Lazily import openai to avoid import cost when not configured
        try:
            import openai
            OPENAI_AVAILABLE = True
        except ImportError:
            OPENAI_AVAILABLE = False
            return None
        
        if OPENAI_AVAILABLE:
            api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
            if api_key:
                try:
                    from openai import OpenAI
                    kwargs: dict[str, Any] = {"api_key": api_key}
                    if base_url := base_url or os.getenv("LLM_BASE_URL"):
                        kwargs["base_url"] = base_url
                    _get_openai_client._client_cache = OpenAI(**kwargs)
                except Exception:
                    _get_openai_client._client_cache = None
    
    return _get_openai_client._client_cache


class MockGenerator:
    """Generates FastAPI mock endpoints from HAR endpoint data.

    Supports two modes:
    - **LLM-assisted** -- when an OpenAI-compatible API key is configured, sends
      endpoint schemas to the model for realistic mock implementations.
    - **Fallback (template)** -- when no LLM is configured, generates stub
      endpoints directly from the HAR response data.

    Args:
        api_key: Optional API key. Falls back to LLM_API_KEY then
                 OPENAI_API_KEY env vars.
        model: Model identifier (default gpt-4o-mini, from MODEL_NAME env).
    """

    # Endpoints always provided by the boilerplate, skipped if present in HAR.
    _BUILTIN_PATHS = {"/health", "/mockclaw/info"}

    def __init__(
        self, api_key: str | None = None, model: str | None = None
    ) -> None:
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv(
            "OPENAI_API_KEY"
        )
        self.model = model or os.getenv("MODEL_NAME", "gpt-4o-mini")
        self._base_url = os.getenv("LLM_BASE_URL")
        self.client: Any = None

        if OPENAI_AVAILABLE and self.api_key:
            self.client = _get_openai_client(self.api_key, self._base_url)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _build_prompt(self, endpoint_data: dict[str, Any]) -> str:
        req = endpoint_data.get("sample_request", {})
        resp = endpoint_data.get("sample_response", {})
        return (
            f"Generate a FastAPI mock endpoint for:\n\n"
            f"Method: {endpoint_data['method']}\n"
            f"Path: {endpoint_data['resource_path']}\n\n"
            f"Sample Request:\n"
            f"- Body: {req.get('body', 'N/A')}\n"
            f"- Query Params: {json.dumps(req.get('query_params', {}), indent=2)}\n\n"
            f"Sample Response:\n"
            f"- Status: {resp.get('status', 200)}\n"
            f"- Body: {resp.get('body', 'N/A')}"
        )

    @staticmethod
    def _extract_code_block(response: str) -> str:
        if match := re.search(r"```python\n(.*?)```", response, re.DOTALL):
            return match.group(1).strip()
        if match := re.search(r"```\n?(.*?)```", response, re.DOTALL):
            return match.group(1).strip()
        return response.strip()

    def _generate_with_llm(self, endpoint_data: dict[str, Any]) -> str:
        if not self.client:
            return self._generate_fallback_code(endpoint_data)
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._build_prompt(endpoint_data)},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            return self._extract_code_block(
                response.choices[0].message.content or ""
            )
        except Exception:
            return self._generate_fallback_code(endpoint_data)

    # ------------------------------------------------------------------
    # Fallback path
    # ------------------------------------------------------------------

    def _generate_fallback_code(self, endpoint_data: dict[str, Any]) -> str:
        method = endpoint_data["method"]
        path = endpoint_data["resource_path"]
        all_responses: list[dict[str, Any]] = endpoint_data.get(
            "sample_responses",
            [endpoint_data.get("sample_response", {})],
        )
        func_name = "_".join(
            filter(
                None,
                [
                    method.lower(),
                    path.replace("/", "_")
                    .replace("{", "")
                    .replace("}", ""),
                ],
            )
        )
        return _route_from_responses(method, path, all_responses, func_name)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_endpoint(
        self, endpoint_data: dict[str, Any]
    ) -> GenerationResult:
        try:
            code = self._generate_with_llm(endpoint_data)
            if "from fastapi import" not in code:
                code = (
                    "from fastapi import HTTPException, status\n"
                    "from typing import Any\n\n"
                    + code
                )
            return GenerationResult(
                success=True,
                generated_code=code,
                endpoint_path=endpoint_data["resource_path"],
            )
        except Exception as e:  # pragma: no cover
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
    ) -> list[GenerationResult]:
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)

        results: list[GenerationResult] = []

        header = [
            "# MockClaw Auto-Generated Mock Server",
            "# Do not edit manually -- regenerate from HAR traffic.",
            "",
            "from fastapi import FastAPI, HTTPException, status, Request, Response",
            "from fastapi.responses import JSONResponse",
            "from typing import Any",
            "from starlette.middleware.base import BaseHTTPMiddleware",
            "import re",
            "import time",
            "from collections import defaultdict",
            "",
            "app = FastAPI(title='MockClaw Generated API')",
            "",
            "# === Resilience Middleware (Auto-Injected) ===",
            "",
            "class PathTraversalMiddleware(BaseHTTPMiddleware):",
            "    async def dispatch(self, request: Request, call_next):",
            "        path = request.url.path",
            "        dangerous = [r'\\.\\.', '%2e%2e', '%252e', '%2f%5c.\\.', '//']",
            "        for pattern in dangerous:",
            "            if re.search(pattern, path, re.IGNORECASE):",
            "                return JSONResponse(status_code=400, content={'error': 'Invalid path', 'code': 'PATH_TRAVERSAL_BLOCKED'})",
            "        return await call_next(request)",
            "",
            "class RateLimitMiddleware(BaseHTTPMiddleware):",
            "    def __init__(self, app, requests_per_minute: int = 60):",
            "        super().__init__(app)",
            "        self.requests_per_minute = requests_per_minute",
            "        self.request_counts = defaultdict(list)",
            "    async def dispatch(self, request: Request, call_next):",
            "        client_ip = request.client.host if request.client else 'unknown'",
            "        current_time = time.time()",
            "        self.request_counts[client_ip] = [t for t in self.request_counts[client_ip] if current_time - t < 60]",
            "        if len(self.request_counts[client_ip]) >= self.requests_per_minute:",
            "            return JSONResponse(status_code=429, content={'error': 'Too many requests', 'code': 'RATE_LIMIT_EXCEEDED'})",
            "        self.request_counts[client_ip].append(current_time)",
            "        return await call_next(request)",
            "",
            "class GlobalErrorHandler(BaseHTTPMiddleware):",
            "    async def dispatch(self, request: Request, call_next):",
            "        try:",
            "            return await call_next(request)",
            "        except HTTPException as e:",
            "            return JSONResponse(status_code=e.status_code, content={'error': str(e.detail), 'code': 'HTTP_ERROR'})",
            "        except Exception as e:",
            "            return JSONResponse(status_code=500, content={'error': 'Internal server error', 'code': 'INTERNAL_ERROR'})",
            "",
            "# Apply middleware",
            "app.add_middleware(GlobalErrorHandler)",
            "app.add_middleware(RateLimitMiddleware, requests_per_minute=60)",
            "app.add_middleware(PathTraversalMiddleware)",
            "",
            '@app.get("/health")',
            "async def health():",
            f"{_FB}'''Health check endpoint.'''",
            f'{_FB}return {{"status": "OK", "service": "MockClaw"}}',
            "",
            '@app.get("/mockclaw/info")',
            "async def info():",
            f"{_FB}'''MockClaw metadata endpoint.'''",
            f'{_FB}return {{"generator": "MockClaw", "version": "0.1.0"}}',
            "",
            "# === Generated Endpoints ===",
            "",
        ]

        for endpoint in endpoints:
            if endpoint["resource_path"] in self._BUILTIN_PATHS:
                continue
            result = self.generate_endpoint(endpoint)
            results.append(result)
            if result.success:
                header.append(
                    f"# {endpoint['method']} {endpoint['resource_path']}"
                )
                header.append(result.generated_code)
                header.append("")

        (output_path / "dynamic_api.py").write_text(
            "\n".join(header), encoding="utf-8"
        )
        return results


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI for testing generation."""
    import sys

    if len(sys.argv) < 2:
        print("Usage: python generator.py <path_to_har_file>")
        sys.exit(1)

    from core.parser import HARParser

    parser = HARParser(sys.argv[1])
    endpoints_data = parser.export_as_dict()
    generator = MockGenerator()
    results = generator.generate_all(endpoints_data["endpoints"])

    print(f"Generated {len(results)} endpoints:")
    for r in results:
        symbol = "OK" if r.success else "FAIL"
        print(f"  [{symbol}] {r.endpoint_path}")


if __name__ == "__main__":
    main()
