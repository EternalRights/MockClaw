"""
MockClaw Route Builder
Builds FastAPI route strings from HAR response data.
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

_FB = "    "

_logger = logging.getLogger(__name__)


def _return_line(status: int, body_expr: str, indent: str = _FB) -> str:
    """Build the statement that replays one recorded response.

    Every recorded status and body is replayed through one path so the mock
    answers exactly what the HAR captured. Returning the bare literal always
    answered 200, misreporting a recorded 201, 204 or 302; raising
    HTTPException did set the status but wrapped the body in ``{"detail":
    ...}``. A plain 200 keeps the direct return; anything else goes out via
    ``JSONResponse`` with the recorded status code and the recorded body.
    """
    if status == 200:
        return f"{indent}return {body_expr}"
    return f"{indent}return JSONResponse(status_code={status}, content={body_expr})"


def _py_literal(value: Any) -> str:
    """Render a JSON value as a runnable Python literal.

    ``json.dumps`` (and ``orjson``) emit ``null``/``true``/``false`` which are
    not Python literals and would NameError inside generated route code. Recurse
    through the value so nested dicts/lists come out as valid Python too.
    """
    if value is None:
        return "None"
    if value is True:
        return "True"
    if value is False:
        return "False"
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (int, float)):
        return repr(value)
    if isinstance(value, list):
        return "[" + ", ".join(_py_literal(v) for v in value) + "]"
    if isinstance(value, dict):
        items = ", ".join(
            f"{json.dumps(k, ensure_ascii=False)}: {_py_literal(v)}"
            for k, v in value.items()
        )
        return "{" + items + "}"
    return json.dumps(value, ensure_ascii=False)


def body_literal(body_text: str) -> str:
    """Compact Python literal from raw HAR body text."""
    try:
        parsed = json.loads(body_text)
        return _py_literal(parsed)
    except (json.JSONDecodeError, TypeError) as exc:
        _logger.debug("body_literal: non-JSON body, returning raw string: %s", exc)
        return json.dumps(body_text)


def _docstring_safe(text: str) -> str:
    """Escape raw HAR body text before it goes into a triple-quoted docstring.

    Scenario listings embed raw response bodies. A body containing ``\"\"\"``
    terminates the docstring early, and a backslash can escape the closing
    quotes; either way the generated module raises ``SyntaxError`` and the
    whole mock server refuses to start, not just that one endpoint.

    Backslashes are escaped first so the text still *reads* as the raw body:
    a JSON body's ``\\"\\"\\"`` is displayed as ``\\"\\"\\"``, exactly as
    captured, instead of collapsing into triple quotes.
    """
    return text.replace("\\", "\\\\").replace('"""', '\\"\\"\\"')


def _latency_line(latency_ms: int, indent: str = _FB) -> str:
    """Build an ``await asyncio.sleep()`` line to simulate response latency."""
    if latency_ms <= 0:
        return ""
    seconds = latency_ms / 1000.0
    return f"{indent}await asyncio.sleep({seconds:.3f})\n"


# Verbs FastAPI's app exposes a decorator helper for. Anything else -- WebDAV's
# PROPFIND/MKCOL, for instance -- has no such attribute, so emitting
# ``@app.propfind(...)`` kills the whole generated module with AttributeError
# on import, taking every other route down with it.
_APP_VERBS = frozenset({
    "GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS", "TRACE",
})


def _route_decorator(method: str, path: str) -> str:
    """Build the decorator line that registers *path* under *method*.

    Falls back to ``api_route`` for methods FastAPI has no shorthand for.
    """
    if method in _APP_VERBS:
        return f'@app.{method.lower()}("{path}")'
    return f'@app.api_route("{path}", methods=["{method}"])'


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
    # Direct callers may hand over "post" rather than "POST"; the smart-router
    # guards below compare against upper-case names.
    method = (method or "").strip().upper()

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
            _route_decorator(method, path) + "\n"
            f"async def {func_name}():\n"
            f'{_FB}"""Mock endpoint -- no HAR response data."""\n'
            f"{latency}"
            f"{_FB}return {{}}\n"
        )

    sc0 = all_responses[0].get("status", 200)
    body0 = body_literal(all_responses[0].get("body") or "")

    body_code = _return_line(sc0, body0)

    if len(all_responses) > 1:
        lines = [
            _route_decorator(method, path),
            f"async def {func_name}():",
            f'{_FB}"""Mock endpoint -- {len(all_responses)} HAR scenarios recorded.',
        ]
        for i, resp in enumerate(all_responses, start=1):
            sc = resp.get("status", 200)
            preview = _docstring_safe((resp.get("body") or "")[:60])
            lines.append(f'{_FB}  [{i}] status {sc}: {preview}')
        lines.append(f'{_FB}"""')
        if latency:
            lines.append(latency.rstrip("\n"))
        lines.append(body_code)
        return "\n".join(lines) + "\n"

    return (
        _route_decorator(method, path) + "\n"
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
        _route_decorator(method, path),
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
            (
                f'body.get("{field}") == {_py_literal(req_data[field])}'
                if field in req_data
                else f'body.get("{field}") is None'
            )
            for field in fields
        ]
        condition = " and ".join(checks)
        if condition in emitted:
            continue
        emitted.add(condition)

        keyword = "if" if first else "elif"
        first = False
        lines.append(f"{_FB}{keyword} {condition}:")

        resp_literal = body_literal(json.dumps(resp_data))
        lines.append(_return_line(status, resp_literal, _FB * 2))

    default_response = next(
        (resp for resp in all_responses if 200 <= resp.get("status", 200) < 300),
        all_responses[0]
    )
    default_resp = default_response.get("body", "{}")
    default_status = default_response.get("status", 200)
    lines.append(f'{_FB}else:')
    lines.append(_return_line(default_status, body_literal(default_resp), _FB * 2))

    return "\n".join(lines) + "\n"


_KEYWORDS = frozenset({
    "await", "class", "def", "del", "elif", "else", "except", "for",
    "from", "global", "if", "import", "in", "is", "lambda", "not",
    "or", "pass", "raise", "return", "try", "while", "with", "yield",
    "async", "assert", "break", "continue", "finally", "nonlocal",
})

# Names already bound in the generated mock server module (see the header
# template in generator.py). A query parameter using one of these would
# shadow the import and break e.g. status.HTTP_400_... inside a raise branch.
_RESERVED_NAMES = _KEYWORDS | {
    "FastAPI", "HTTPException", "status", "Request", "Response",
    "JSONResponse", "CORSMiddleware", "BaseHTTPMiddleware", "Any",
    "asyncio", "time", "json", "defaultdict", "app",
}


def _safe_param_name(name: str) -> str:
    """Turn a query parameter name into a valid Python argument name.

    HAR captures can contain names like ``user-id``, ``filter[]`` or
    straight-up Python keywords (``class``). None of those survive as
    function arguments, so sanitize and de-keyword them. Names that the
    generated module already imports (``status``, ``app``, ...) are also
    suffixed so the parameter does not shadow them.
    """
    safe = re.sub(r"\W", "_", name)
    if not safe or safe[0].isdigit():
        safe = f"q_{safe}"
    if safe in _RESERVED_NAMES:
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

    For GET endpoints with query parameters, generates a route that accepts
    those parameters as FastAPI function arguments and, when multiple
    responses are observed, emits conditional branches keyed on the
    parameter values that separate them.
    """
    latency = _latency_line(latency_ms)

    if not sample_request:
        return build_route(method, path, all_responses, func_name, use_smart_fallback=False, latency_ms=latency_ms)

    query_params = sample_request.get("query_params", {})
    if not query_params:
        return build_route(method, path, all_responses, func_name, use_smart_fallback=False, latency_ms=latency_ms)

    # Collect each response's query params and find the fields that separate
    # them, mirroring the body-based smart routing logic.
    distinct: list[tuple[dict[str, Any], int, str]] = []
    for resp in all_responses:
        qp = resp.get("request", {}).get("query_params", {})
        if qp:
            distinct.append((qp, resp.get("status", 200), resp.get("body") or "{}"))

    distinct = _dedupe_requests(distinct)

    all_fields: list[str] = []
    for qp, _, _ in distinct:
        for field in qp:
            if field not in all_fields:
                all_fields.append(field)

    fields = _select_discriminating_fields(distinct, all_fields) if len(distinct) >= 2 else []

    # Declare the sampled params plus any key a branch might test. A later
    # response can carry query keys the sampled request did not, and a branch
    # referencing an undeclared name would NameError in the generated server.
    param_names = list(query_params.keys())
    for field in all_fields:
        if field not in param_names:
            param_names.append(field)

    lines = [
        _route_decorator(method, path),
        f"async def {func_name}(",
    ]

    for param in param_names:
        default_val = query_params.get(param, "")
        # json.dumps handles quotes/backslashes/newlines inside the value;
        # a plain f-string interpolation would emit broken Python.
        default_literal = json.dumps(str(default_val))
        lines.append(f"{_FB}{_safe_param_name(param)}: str = {default_literal},")
    lines.append(f"):")

    if len(all_responses) > 1:
        lines.append(f'{_FB}"""Mock endpoint with query parameter support.')
        for i, resp in enumerate(all_responses, start=1):
            sc = resp.get("status", 200)
            preview = _docstring_safe((resp.get("body") or "")[:60])
            lines.append(f'{_FB}  [{i}] status {sc}: {preview}')
        lines.append(f'{_FB}"""')
    else:
        lines.append(f'{_FB}"""Mock endpoint with query parameter support."""')

    if latency:
        lines.append(latency.rstrip("\n"))

    if fields:
        emitted: set[str] = set()
        first = True
        for qp, status_, resp_body in distinct:
            checks = [
                f'{_safe_param_name(field)} == {_py_literal(qp[field])}'
                for field in fields
                if field in qp
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

            resp_literal = body_literal(resp_body)
            lines.append(_return_line(status_, resp_literal, _FB * 2))

        default_response = next(
            (resp for resp in all_responses if 200 <= resp.get("status", 200) < 300),
            all_responses[0],
        )
        default_status = default_response.get("status", 200)
        default_literal = body_literal(default_response.get("body") or "{}")
        lines.append(f'{_FB}else:')
        lines.append(_return_line(default_status, default_literal, _FB * 2))
    else:
        sc0 = all_responses[0].get("status", 200)
        body0 = body_literal(all_responses[0].get("body") or "{}")
        lines.append(_return_line(sc0, body0))

    return "\n".join(lines) + "\n"


def generate_func_name(method: str, path: str) -> str:
    """Build a valid Python function name from HTTP method and path."""
    name = method.lower() + "_" + path.replace("/", "_").replace("{", "").replace("}", "")
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    return "_".join(filter(None, name.split("_")))
