"""
MockClaw Route Builder
Builds FastAPI route strings from HAR response data.
"""

from __future__ import annotations

import json
import logging
from typing import Any

try:
    import orjson
    HAS_ORJSON = True
except ImportError:
    orjson = None
    HAS_ORJSON = False

_STATUS_EXC = {
    400: "HTTP_400_BAD_REQUEST",
    401: "HTTP_401_UNAUTHORIZED",
    403: "HTTP_403_FORBIDDEN",
    404: "HTTP_404_NOT_FOUND",
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


def build_route(
    method: str,
    path: str,
    all_responses: list[dict[str, Any]],
    func_name: str,
    use_smart_fallback: bool = False,
) -> str:
    """Build a complete FastAPI route string for one endpoint.

    When multiple responses exist, the first (default) response is used at
    runtime and the docstring lists all observed HAR scenarios for reference.

    If *use_smart_fallback* is ``True``, generates conditional routing based
    on request body fields (e.g. coupon codes).
    """
    has_request_body = any(
        resp.get("request", {}).get("body")
        for resp in all_responses
    )

    if use_smart_fallback and has_request_body and method in ["POST", "PUT"]:
        return _generate_smart_route(method, path, all_responses, func_name)

    if not all_responses:
        return (
            f'@app.{method.lower()}("{path}")\n'
            f"async def {func_name}():\n"
            f'{_FB}"""Mock endpoint -- no HAR response data."""\n'
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
    """Generate route with conditional logic based on request body analysis.

    Automatically analyzes multiple request bodies to find fields with
    differing values, then generates if/elif/else routing logic.
    No hardcoded field names -- works with any JSON request body.
    """
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
        return build_route(method, path, all_responses, func_name, use_smart_fallback=False)

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
        return build_route(method, path, all_responses, func_name, use_smart_fallback=False)

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
        f'{_FB}body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {{}}',
        "",
    ]

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


def generate_func_name(method: str, path: str) -> str:
    """Build a valid Python function name from HTTP method and path."""
    return "_".join(
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
