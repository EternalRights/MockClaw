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


def _dedupe_requests(
    parsed: list[tuple[dict[str, Any], int, Any]],
) -> list[tuple[dict[str, Any], int, Any]]:
    """Collapse duplicate request bodies, keeping the first response.

    Two entries with the same JSON body should route to one response, so a
    repeated body is dropped after the first occurrence.
    """
    seen: dict[str, tuple[dict[str, Any], int, Any]] = {}
    for req, status, resp in parsed:
        key = json.dumps(req, sort_keys=True)
        if key not in seen:
            seen[key] = (req, status, resp)
    return list(seen.values())


def _select_discriminating_fields(
    distinct: list[tuple[dict[str, Any], int, Any]],
    all_fields: list[str],
) -> list[str]:
    """Pick the smallest field set that separates every distinct response.

    Greedy: start with no fields, then keep adding the field that resolves
    the most remaining "different response, same key" collisions until no
    pair of distinct responses shares a key, or the fields run out. This is
    what lets routing work when a single field is not enough, e.g. requests
    that differ only on a secondary field like ``region`` while ``role``
    stays the same.
    """
    n = len(distinct)
    resp_sig = [
        (status, json.dumps(resp, sort_keys=True))
        for _, status, resp in distinct
    ]

    def keys(fields: list[str]) -> list[tuple]:
        return [tuple(req.get(f) for f in fields) for req, _, _ in distinct]

    def collisions(fields: list[str]) -> set:
        ks = keys(fields)
        pairs = set()
        for i in range(n):
            for j in range(i + 1, n):
                if resp_sig[i] != resp_sig[j] and ks[i] == ks[j]:
                    pairs.add((i, j))
        return pairs

    selected: list[str] = []
    current = collisions(selected)
    remaining = list(all_fields)
    while current and remaining:
        best_field: str | None = None
        best_broken = -1
        for field in remaining:
            after = collisions(selected + [field])
            broken = len(current) - len(after)
            if broken > best_broken:
                best_broken = broken
                best_field = field
        if best_field is None or best_broken == 0:
            break
        selected.append(best_field)
        remaining.remove(best_field)
        current = collisions(selected)
    return selected


def _generate_smart_route(
    method: str,
    path: str,
    all_responses: list[dict[str, Any]],
    func_name: str,
    latency_ms: int = 0,
) -> str:
    """Generate route with conditional logic based on request body analysis.

    Automatically analyzes multiple request bodies to find the fields that
    separate them, then generates if/elif/else routing. When one field is
    not enough to tell two responses apart, the discriminator adds further
    fields and joins their checks with ``and``. No hardcoded field names.
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

    distinct = _dedupe_requests(parsed_requests)

    if len(distinct) < 2:
        return build_route(method, path, all_responses, func_name, use_smart_fallback=False, latency_ms=latency_ms)

    all_fields: list[str] = []
    for req_data, _, _ in distinct:
        for field in req_data:
            if field not in all_fields:
                all_fields.append(field)

    fields = _select_discriminating_fields(distinct, all_fields)

    if not fields:
        return build_route(method, path, all_responses, func_name, use_smart_fallback=False, latency_ms=latency_ms)

    lines = [
        f'@app.{method.lower()}("{path}")',
        f"async def {func_name}(request: Request):",
        f'{_FB}"""Smart mock endpoint with conditional routing."""',
    ]
    if latency:
        lines.append(latency.rstrip("\n"))
    lines.append(f'{_FB}body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {{}}')
    lines.append("")

    emitted: set[str] = set()
    first = True
    for req_data, status, resp_data in distinct:
        checks = [
            f'body.get("{field}") == {json.dumps(req_data[field])}'
            for field in fields
            if field in req_data
        ]
        if not checks:
            continue
        condition = " and ".join(checks)
        if condition in emitted:
            continue
        emitted.add(condition)

        keyword = "if" if first else "elif"
        first = False
        lines.append(f"{_FB}{keyword} {condition}:")

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
