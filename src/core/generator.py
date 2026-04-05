"""
MockClaw AI Generator
Uses LLM to generate FastAPI mock endpoints from parsed HAR data.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any

# Use orjson for 2-5x faster JSON serialization if available
try:
    import orjson
    HAS_ORJSON = True
except ImportError:
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
        """Initialize generation result.

        Args:
            success: Whether the generation was successful.
            generated_code: The generated FastAPI code (empty if failed).
            endpoint_path: The API endpoint path.
            error: Error message if generation failed, None otherwise.
        """
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
    use_smart_fallback: bool = False,
) -> str:
    """Build a complete FastAPI route string for one endpoint.

    When multiple responses exist, the first (default) response is used at
    runtime and the docstring lists all observed HAR scenarios for reference.
    
    If use_smart_fallback is True, generates conditional routing based on
    request body fields (e.g., coupon codes).
    """
    # Check if we have POST/PUT data to enable smart routing
    has_request_body = any(
        resp.get("request", {}).get("body") 
        for resp in all_responses
    )
    
    # For POST/PUT requests with body, use smart routing if enabled
    if use_smart_fallback and has_request_body and method in ["POST", "PUT"]:
        return _generate_smart_route(method, path, all_responses, func_name)
    
    # Default behavior: use first response
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


def _generate_smart_route(
    method: str,
    path: str,
    all_responses: list[dict[str, Any]],
    func_name: str,
) -> str:
    """Generate route with conditional logic based on request body.
    
    Analyzes HAR entries to find distinguishing fields (like 'coupon')
    and generates if/elif chains to route to appropriate responses.
    """
    # Collect unique request bodies and their responses
    # Use dict to deduplicate by (field, value) key - first occurrence wins
    request_patterns_dict: dict[tuple[str, Any], dict[str, Any]] = {}
    
    for resp in all_responses:
        req_body = resp.get("request", {}).get("body", "")
        resp_status = resp.get("status", 200)
        resp_body = resp.get("body", "")
        
        if req_body:
            try:
                req_data = json.loads(req_body) if isinstance(req_body, str) else req_body
                resp_data = json.loads(resp_body) if isinstance(resp_body, str) else resp_body
                
                # Look for key distinguishing fields
                for field in ["coupon", "coupon_code", "status", "type", "action"]:
                    if field in req_data:
                        field_value = req_data[field]
                        key = (field, field_value)
                        
                        # Only add if we haven't seen this (field, value) combination
                        # This prevents duplicate IF conditions
                        if key not in request_patterns_dict:
                            request_patterns_dict[key] = {
                                "field": field,
                                "value": field_value,
                                "status": resp_status,
                                "response": resp_data,
                                "request": req_data,
                            }
                        break
            except (json.JSONDecodeError, TypeError):
                continue
    
    # Convert back to list, preserving order of first occurrence
    request_patterns = list(request_patterns_dict.values())
    
    # If we found patterns, generate conditional routing
    if request_patterns:
        lines = [
            f'@app.{method.lower()}("{path}")',
            f"async def {func_name}(request: Request):",
            f'{_FB}"""Smart mock endpoint with conditional routing."""',
            f'{_FB}body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {{}}',
            "",
        ]
        
        # Group by field for cleaner if/elif chains
        field_groups = {}
        for pattern in request_patterns:
            field = pattern["field"]
            if field not in field_groups:
                field_groups[field] = []
            field_groups[field].append(pattern)
        
        # Generate if/elif for the first field (most common)
        primary_field = list(field_groups.keys())[0]
        patterns_for_field = field_groups[primary_field]
        
        for i, pattern in enumerate(patterns_for_field):
            if i == 0:
                lines.append(f'{_FB}if body.get("{pattern["field"]}") == {json.dumps(pattern["value"])}:')
            else:
                lines.append(f'{_FB}elif body.get("{pattern["field"]}") == {json.dumps(pattern["value"])}:')
            
            # Add response logic
            if 400 <= pattern["status"] < 600:
                exc = _STATUS_EXC.get(pattern["status"], "HTTP_500_INTERNAL_SERVER_ERROR")
                resp_literal = _body_literal(json.dumps(pattern["response"]))
                lines.append(f'{_FB}    raise HTTPException(status_code=status.{exc}, detail={resp_literal})')
            else:
                resp_literal = _body_literal(json.dumps(pattern["response"]))
                lines.append(f'{_FB}    return {resp_literal}')
        
        # Add fallback (default response - prefer SUCCESS over ERROR)
        # Find first 2xx response, otherwise use first response
        default_response = next(
            (resp for resp in all_responses if 200 <= resp.get("status", 200) < 300),
            all_responses[0]
        )
        default_resp = default_response.get("body", "{}")
        default_status = default_response.get("status", 200)
        lines.append(f'{_FB}else:')
        if 400 <= default_status < 600:
            exc = _STATUS_EXC.get(default_status, "HTTP_500_INTERNAL_SERVER_ERROR")
            lines.append(f'{_FB}    raise HTTPException(status_code=status.{exc}, detail={_body_literal(default_resp)})')
        else:
            lines.append(f'{_FB}    return {_body_literal(default_resp)}')
        
        return "\n".join(lines) + "\n"
    
    # No patterns found, fall back to simple routing
    return _route_from_responses(method, path, all_responses, func_name, use_smart_fallback=False)


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
    - **Smart Fallback** -- when use_smart_fallback=True, analyzes request bodies
      to generate conditional routing logic (e.g., different responses for different coupon codes).

    Args:
        api_key: Optional API key. Falls back to LLM_API_KEY then
                 OPENAI_API_KEY env vars.
        model: Model identifier (default gpt-4o-mini, from MODEL_NAME env).
    """

    # Endpoints always provided by the boilerplate, skipped if present in HAR.
    _BUILTIN_PATHS = {"/health", "/mockclaw/info"}

    def __init__(
        self, 
        api_key: str | None = None, 
        model: str | None = None,
        use_smart_fallback: bool = False,
    ) -> None:
        """Initialize the MockGenerator.

        Args:
            api_key: Optional API key for LLM. Falls back to LLM_API_KEY
                then OPENAI_API_KEY environment variables.
            model: Model identifier for LLM. Defaults to gpt-4o-mini or
                MODEL_NAME environment variable.
            use_smart_fallback: Enable smart routing based on request body
                analysis (e.g., different responses for different coupon codes).
        """
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv(
            "OPENAI_API_KEY"
        )
        self.model = model or os.getenv("MODEL_NAME", "gpt-4o-mini")
        self._base_url = os.getenv("LLM_BASE_URL")
        self.use_smart_fallback = use_smart_fallback
        self.client: Any = None

        if OPENAI_AVAILABLE and self.api_key:
            self.client = _get_openai_client(self.api_key, self._base_url)

    # ------------------------------------------------------------------
    # LLM path
    # ------------------------------------------------------------------

    def _build_prompt(self, endpoint_data: dict[str, Any]) -> str:
        """Build the LLM prompt for endpoint generation.

        Args:
            endpoint_data: Dictionary containing endpoint information including
                method, path, sample request, and sample response.

        Returns:
            Formatted prompt string for the LLM.
        """
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
        """Extract Python code from LLM response.

        Args:
            response: Raw LLM response text.

        Returns:
            Extracted Python code, or original response if no code block found.
        """
        if match := re.search(r"```python\n(.*?)```", response, re.DOTALL):
            return match.group(1).strip()
        if match := re.search(r"```\n?(.*?)```", response, re.DOTALL):
            return match.group(1).strip()
        return response.strip()

    def _generate_with_llm(self, endpoint_data: dict[str, Any]) -> str:
        """Generate mock endpoint code using LLM.

        Args:
            endpoint_data: Dictionary containing endpoint information.

        Returns:
            Generated FastAPI code. Falls back to template generation if
            LLM is unavailable or fails.
        """
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
        """Generate mock endpoint code using template fallback.

        Creates a simple FastAPI route that returns the HAR response data
        directly, optionally with smart routing based on request body.

        Args:
            endpoint_data: Dictionary containing endpoint information including
                method, path, sample request, and all observed responses.

        Returns:
            Generated FastAPI route code.
        """
        method = endpoint_data["method"]
        path = endpoint_data["resource_path"]
        sample_request = endpoint_data.get("sample_request", {})
        all_responses: list[dict[str, Any]] = endpoint_data.get(
            "sample_responses",
            [endpoint_data.get("sample_response", {})],
        )
        
        # Only attach sample_request body if responses don't already have their own request bodies
        # (Parser now exports request body per-response for smart routing)
        has_individual_requests = any(
            resp.get("request") and resp["request"].get("body")
            for resp in all_responses
        )
        
        if not has_individual_requests:
            # Fallback: use sample_request for all responses (old behavior)
            request_body = sample_request.get("body")
            if request_body:
                for resp in all_responses:
                    resp["request"] = {"body": request_body}
        
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
        return _route_from_responses(
            method, 
            path, 
            all_responses, 
            func_name,
            use_smart_fallback=self.use_smart_fallback,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_endpoint(
        self, endpoint_data: dict[str, Any]
    ) -> GenerationResult:
        """Generate a single mock endpoint.

        Args:
            endpoint_data: Dictionary containing endpoint information including
                method, resource_path, sample_request, and sample_response(s).

        Returns:
            GenerationResult containing success status, generated code,
            endpoint path, and any error message.
        """
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
        use_smart_fallback: bool | None = None,
    ) -> list[GenerationResult]:
        """Generate all mock endpoints.
        
        Args:
            endpoints: List of endpoint data from HAR parser
            output_dir: Directory to write generated code
            use_smart_fallback: Override instance setting for smart routing
        """
        # Allow per-call override of smart_fallback setting
        if use_smart_fallback is not None:
            old_setting = self.use_smart_fallback
            self.use_smart_fallback = use_smart_fallback
        else:
            old_setting = None
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
            "import json",
            "from collections import defaultdict",
            "",
            "app = FastAPI(title='MockClaw Generated API')",
            "",
            "# === Resilience Middleware (Auto-Injected) ===",
            "",
            "class PathTraversalMiddleware(BaseHTTPMiddleware):",
            "    async def dispatch(self, request: Request, call_next):",
            "        path = request.url.path",
            r"        dangerous = [r'\.\.', r'%2e%2e', r'%252e', r'%2f%5c\.\.', '//']",
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

        # Restore original setting if we overrode it
        if old_setting is not None:
            self.use_smart_fallback = old_setting

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
