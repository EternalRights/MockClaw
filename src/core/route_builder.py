"""
MockClaw Route Builder
Builds FastAPI route strings from HAR response data.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any
from urllib.parse import urlparse, parse_qs

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    orjson = None
    HAS_ORJSON = False

_STATUS_EXC = {
    400: "HTTP_400_BAD_REQUEST",
    401: "HTTP_401_UNAUTHORIZED",
    402: "HTTP_402_PAYMENT_REQUIRED",
    403: "HTTP_403_FORBIDDEN",
    404: "HTTP_404_NOT_FOUND",
    405: "HTTP_405_METHOD_NOT_ALLOWED",
    406: "HTTP_406_NOT_ACCEPTABLE",
    408: "HTTP_408_REQUEST_TIMEOUT",
    409: "HTTP_409_CONFLICT",
    410: "HTTP_410_GONE",
    411: "HTTP_411_LENGTH_REQUIRED",
    412: "HTTP_412_PRECONDITION_FAILED",
    413: "HTTP_413_REQUEST_ENTITY_TOO_LARGE",
    415: "HTTP_415_UNSUPPORTED_MEDIA_TYPE",
    422: "HTTP_422_UNPROCESSABLE_ENTITY",
    429: "HTTP_429_TOO_MANY_REQUESTS",
    500: "HTTP_500_INTERNAL_SERVER_ERROR",
    501: "HTTP_501_NOT_IMPLEMENTED",
    502: "HTTP_502_BAD_GATEWAY",
    503: "HTTP_503_SERVICE_UNAVAILABLE",
    504: "HTTP_504_GATEWAY_TIMEOUT",
}

_FB = "    "

_logger = logging.getLogger(__name__)


def body_literal(body_text: str) -> str:
    """Compact JSON string literal from raw HAR body text."""
    try:
        parsed = json.loads(body_text)
        if HAS_ORJSON:
            return orjson.dumps(parsed).decode('utf-8')
        return json.dumps(parsed, ensure_ascii=False)
    except (json.JSONDecodeError, TypeError) as exc:
        _logger.debug("body_literal: non-JSON body, returning raw string: %s", exc)
        return json.dumps(body_text)


def _extract_query_params(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    if not parsed.query:
        return {}
    params: dict[str, str] = {}
    for key, values in parse_qs(parsed.query).items():
        params[key] = values[0]
    return params


def _latency_line(latency_ms: int, indent: str = _FB) -> str:
    """Build an ``await asyncio.sleep()`` line to simulate response latency."""
    if latency_ms <= 0:
        return ""
    seconds = latency_ms / 1000.0
    return f"{indent}await asyncio.sleep({seconds:.3f})\n"


def build_route(
    method: str,
    path: str,
    all_responses: list[dict[str, Any]],
    func_name: str,
    use_smart_fallback: bool = False,
    sample_request: dict[str, Any] | None = None,
    latency_ms: int = 0,
) -> str:
    """Build a complete FastAPI route string for one endpoint.

    When multiple responses exist, the first (default) response is used at
    runtime and the docstring lists all observed HAR scenarios for reference.

    If *use_smart_fallback* is ``True``, generates conditional routing based
    on request body fields or query parameters.

    If *latency_ms* is positive, injects an ``await asyncio.sleep()`` into the
    handler to mimic the original response time recorded in the HAR file.
    """
    latency = _latency_line(latency_ms)

    has_request_body = any(
        resp.get("request", {}).get("body")
        for resp in all_responses
    )

    has_query_params = bool(
        sample_request and sample_request.get("query_params")
    )

    if use_smart_fallback and method in ["POST", "PUT", "PATCH", "DELETE"] and has_request_body:
        return _generate_smart_route(method, path, all_responses, func_name, latency_ms)

    if use_smart_fallback and method == "GET" and has_query_params and len(all_responses) > 1:
        return _generate_query_route(method, path, all_responses, func_name, sample_request, latency_ms)

    if not all_responses:
        return (
            f'@app.{method.lower()}("{path}")\n'
            f"async def {func_name}():\n"
            f'{_FB}"""Mock endpoint -- no HAR response data."""\n'
            f"{latency}"
            f"{_FB}return {{}}\n"
        )

    sc0 = all_responses[0].get("status", 200)
    body0 = body_literal(all_responses[0].get("body") or "")

    if 400 <= sc0 < 600:
        exc = _STATUS_EXC.get(sc0, "HTTP_500_INTERNAL_SERVER_ERROR")
        body_code = f"{_FB}raise HTTPException(status_code=status.{exc},detail={body0})"
    else:
        body_code = f"{_FB}return {body0}"

    if len(all_responses) > 1:
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
        if latency:
            lines.append(latency.rstrip("\n"))
        lines.append(body_code)
        return "\n".join(lines) + "\n"

    return (
        f'@app.{method.lower()}("{path}")\n'
        f"async def {func_name}():\n"
        f'{_FB}"""Mock endpoint -- HAR status {sc0}."""\n'
        f"{latency}"
        f"{body_code}\n"
    )


def _generate_smart_route(
    method: str,
    path: str,
    all_responses: list[dict[str, Any]],
    func_name: str,
    latency_ms: int = 0,
) -> str:
    """Generate route with conditional logic based on request body analysis.

    Automatically analyzes multiple request bodies to find fields with
    differing values, then generates if/elif/else routing logic.
    No hardcoded field names -- works with any JSON request body.
    """
    latency = _latency_line(latency_ms)

    parsed_requests: list[tuple[dict[str, Any], int, Any]] = []

    for resp in all_responses:
        req_body = resp.get("request", {}).get("body", "")
        resp_status = resp.get("status", 200)
        resp_body = resp.get("body", "")

        if req_body:
            try:
                req_data = json.loads(req_body) if isinstance(req_body, str) else req_body
                resp_data = json.loads(resp_body) if isinstance(resp_body, str) else resp_body
                if isinstance(req_data, dict):
                    parsed_requests.append((req_data, resp_status, resp_data))
            except (json.JSONDecodeError, TypeError):
                continue

    if len(parsed_requests) < 2:
        return build_route(method, path, all_responses, func_name, use_smart_fallback=False, latency_ms=latency_ms)

    all_fields: set[str] = set()
    for req_data, _, _ in parsed_requests:
        all_fields.update(req_data.keys())

    field_values: dict[str, list[tuple[Any, int, Any]]] = {}
    for field in all_fields:
        values_seen: list[tuple[Any, int, Any]] = []
        for req_data, resp_status, resp_data in parsed_requests:
            if field in req_data:
                val = req_data[field]
                values_seen.append((val, resp_status, resp_data))
        unique_vals = set(v for v, _, _ in values_seen)
        if len(unique_vals) > 1:
            field_values[field] = values_seen

    if not field_values:
        return build_route(method, path, all_responses, func_name, use_smart_fallback=False, latency_ms=latency_ms)

    best_field = max(
        field_values.keys(),
        key=lambda f: (len(set(v for v, _, _ in field_values[f])), f),
    )

    patterns: list[tuple[Any, int, Any]] = field_values[best_field]
    seen_values: set[Any] = set()
    unique_patterns: list[tuple[Any, int, Any]] = []
    for val, status, resp in patterns:
        if val not in seen_values:
            seen_values.add(val)
            unique_patterns.append((val, status, resp))

    lines = [
        f'@app.{method.lower()}("{path}")',
        f"async def {func_name}(request: Request):",
        f'{_FB}"""Smart mock endpoint with conditional routing."""',
    ]
    if latency:
        lines.append(latency.rstrip("\n"))
    lines.append(f'{_FB}body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {{}}')
    lines.append("")

    for i, (value, status, resp_data) in enumerate(unique_patterns):
        if i == 0:
            lines.append(f'{_FB}if body.get("{best_field}") == {json.dumps(value)}:')
        else:
            lines.append(f'{_FB}elif body.get("{best_field}") == {json.dumps(value)}:')

        if 400 <= status < 600:
            exc = _STATUS_EXC.get(status, "HTTP_500_INTERNAL_SERVER_ERROR")
            resp_literal = body_literal(json.dumps(resp_data))
            lines.append(f'{_FB}    raise HTTPException(status_code=status.{exc}, detail={resp_literal})')
        else:
            resp_literal = body_literal(json.dumps(resp_data))
            lines.append(f'{_FB}    return {resp_literal}')

    default_response = next(
        (resp for resp in all_responses if 200 <= resp.get("status", 200) < 300),
        all_responses[0]
    )
    default_resp = default_response.get("body", "{}")
    default_status = default_response.get("status", 200)
    lines.append(f'{_FB}else:')
    if 400 <= default_status < 600:
        exc = _STATUS_EXC.get(default_status, "HTTP_500_INTERNAL_SERVER_ERROR")
        lines.append(f'{_FB}    raise HTTPException(status_code=status.{exc}, detail={body_literal(default_resp)})')
    else:
        lines.append(f'{_FB}    return {body_literal(default_resp)}')

    return "\n".join(lines) + "\n"


_KEYWORDS = frozenset({
    "await", "class", "def", "del", "elif", "else", "except", "for",
    "from", "global", "if", "import", "in", "is", "lambda", "not",
    "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "async", "assert", "break", "continue", "finally", "nonlocal",
})


def _safe_param_name(name: str) -> str:
    """Turn a query parameter name into a valid Python argument name.

    HAR captures can contain names like ``user-id``, ``filter[]`` or
    straight-up Python keywords (``class``). None of those survive as
    function arguments, so sanitize and de-keyword them.
    """
    safe = re.sub(r"\W", "_", name)
    if not safe or safe[0].isdigit():
        safe = f"q_{safe}"
    if safe in _KEYWORDS:
        safe = f"{safe}_"
    return safe


def _generate_query_route(
    method: str,
    path: str,
    all_responses: list[dict[str, Any]],
    func_name: str,
    sample_request: dict[str, Any] | None = None,
    latency_ms: int = 0,
) -> str:
    """Generate route with query parameter support for GET endpoints.

    For GET endpoints with query parameters, generates a route that
    properly accepts those parameters as FastAPI function arguments
    and supports conditional routing based on parameter values.
    """
    latency = _latency_line(latency_ms)

    if not sample_request:
        return build_route(method, path, all_responses, func_name, use_smart_fallback=False, latency_ms=latency_ms)

    query_params = sample_request.get("query_params", {})
    if not query_params:
        return build_route(method, path, all_responses, func_name, use_smart_fallback=False, latency_ms=latency_ms)

    param_names = list(query_params.keys())

    lines = [
        f'@app.{method.lower()}("{path}")',
        f"async def {func_name}(",
    ]

    for param in param_names:
        default_val = query_params[param]
        # json.dumps handles quotes/backslashes/newlines inside the value;
        # a plain f-string interpolation would emit broken Python.
        default_literal = json.dumps(str(default_val))
        lines.append(f"{_FB}{_safe_param_name(param)}: str = {default_literal},")
    lines.append(f"):")
    lines.append(f'{_FB}"""Mock endpoint with query parameter support."""')

    sc0 = all_responses[0].get("status", 200)
    body0 = body_literal(all_responses[0].get("body") or "{}")

    if len(all_responses) > 1:
        doc_parts = [f'{_FB}"""Mock endpoint with query parameter support.']
        for i, resp in enumerate(all_responses, start=1):
            sc = resp.get("status", 200)
            preview = (resp.get("body") or "")[:60]
            doc_parts.append(f'{_FB}  [{i}] status {sc}: {preview}')
        doc_parts.append(f'{_FB}"""')
        lines.extend(doc_parts)

    if latency:
        lines.append(latency.rstrip("\n"))

    if 400 <= sc0 < 600:
        exc = _STATUS_EXC.get(sc0, f"HTTP_{sc0}_ERROR")
        lines.append(f'{_FB}raise HTTPException(status_code=status.{exc}, detail={body0})')
    else:
        lines.append(f'{_FB}return {body0}')

    return "\n".join(lines) + "\n"


def generate_func_name(method: str, path: str) -> str:
    """Build a valid Python function name from HTTP method and path."""
    name = method.lower() + "_" + path.replace("/", "_").replace("{", "").replace("}", "")
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    return "_".join(filter(None, name.split("_")))
