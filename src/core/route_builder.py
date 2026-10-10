"""
MockClaw Route Builder
Builds FastAPI route strings from HAR response data.
"""

from __future__ import annotations

import json
import logging
import math
import re
from typing import Any
from urllib.parse import urlparse

_FB = "    "

_logger = logging.getLogger(__name__)


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
        # repr() renders a non-finite float as the *name* nan/inf, which is
        # not Python at all: a recorded NaN became `return {"v": nan}` and
        # every request to that endpoint answered 500 with NameError.
        if isinstance(value, float) and not math.isfinite(value):
            return f"float({json.dumps(str(value))})"
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


def _is_json_content_type(content_type: str | None) -> bool:
    """Whether a recorded content type should be replayed as JSON.

    Absent or blank types default to JSON: that is how the generator has
    always behaved and the overwhelming majority of captured APIs are JSON.
    """
    if not content_type:
        return True
    return "json" in content_type.lower()


def _has_non_finite_constant(body_text: str) -> bool:
    """Whether *body_text* is JSON only a lax parser accepts.

    ``json.loads`` takes ``NaN`` and ``Infinity``; the JSON spec and
    Starlette's serialiser (``allow_nan=False``) do not. Such a body cannot
    be handed back as a Python object -- the response raises instead of
    answering -- so it is replayed as the bytes the HAR captured. A body that
    is not JSON at all is left to the content-type decision.
    """
    seen = False

    def _mark(_name: str) -> None:
        nonlocal seen
        seen = True
        return None

    try:
        json.loads(body_text, parse_constant=_mark)
    except (json.JSONDecodeError, TypeError):
        return False
    return seen


# Response headers the mock must NOT copy verbatim.
#
# Hop-by-hop headers are the transport's business. The content-* family
# describes an entity the mock already re-derives: Content-Length is
# recomputed (a stale copy truncates or hangs the response), Content-Type
# comes from the recorded media type, and a HAR stores the *decoded* body, so
# replaying Content-Encoding would claim an encoding the bytes no longer have.
# Date and Server are stamped by the server, and the access-control pair is
# set by the middleware this generator injects -- replaying either produces a
# second copy of a header the app already owns.
_MANAGED_RESPONSE_HEADERS = frozenset({
    "content-length", "content-type", "content-encoding",
    "transfer-encoding", "connection", "keep-alive", "upgrade", "te",
    "trailer", "proxy-authenticate", "proxy-authorization",
    "date", "server",
    "access-control-allow-origin", "access-control-allow-credentials",
})

# RFC 7230 token characters: what a header field name may legally consist of.
_HEADER_NAME_RE = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


def _header_text(value: Any) -> str:
    """Coerce a recorded header value to str, treating null as empty."""
    if value is None:
        return ""
    return value if isinstance(value, str) else str(value)


def _header_items(headers: Any, header_pairs: Any = None) -> list[tuple[str, str]]:
    """The recorded response headers to consider, in order.

    The parser keeps an ordered pair list because a name may legitimately
    repeat -- Set-Cookie does, and the dict it also exposes kept only the last
    one. The dict is still accepted for hand-built responses and older
    callers.
    """
    if isinstance(header_pairs, (list, tuple)) and header_pairs:
        items = []
        for pair in header_pairs:
            if isinstance(pair, (list, tuple)) and len(pair) == 2:
                items.append((_header_text(pair[0]), _header_text(pair[1])))
        return items
    if isinstance(headers, dict):
        return [
            (_header_text(name), _header_text(value))
            for name, value in headers.items()
        ]
    return []


def _replayable_header_pairs(
    headers: Any, header_pairs: Any = None
) -> list[tuple[str, str]]:
    """Filter recorded response headers down to the ones worth replaying.

    Captured headers used to be dropped wholesale, so a mocked 302 carried no
    ``Location`` and a mocked login set no cookie: a client that followed the
    redirect or relied on the session cookie could not be exercised against
    the mock at all. The server-owned ones (see ``_MANAGED_RESPONSE_HEADERS``)
    are skipped, as are names that are not legal tokens and values holding
    CR/LF or NUL -- those either make Starlette reject the response or let a
    captured header smuggle a second one into the wire format.
    """
    replayable: list[tuple[str, str]] = []
    for name, value in _header_items(headers, header_pairs):
        key = name.strip().lower()
        if not key or key in _MANAGED_RESPONSE_HEADERS:
            continue
        if not _HEADER_NAME_RE.match(key):
            continue
        if any(ch in value for ch in "\r\n\x00"):
            continue
        replayable.append((key, value))
    return replayable


def _replay_line(
    status: int,
    body_text: str,
    content_type: str | None = None,
    headers: Any = None,
    header_pairs: Any = None,
    indent: str = _FB,
) -> str:
    """Build the statement that replays one recorded response.

    Every recorded status, body and header set is replayed through one path so
    the mock answers exactly what the HAR captured. Returning the bare literal
    always answered 200, misreporting a recorded 201, 204 or 302; raising
    HTTPException did set the status but wrapped the body in ``{"detail":
    ...}``. A plain 200 with nothing to add keeps the direct return; anything
    else goes out through ``JSONResponse`` (or ``Response``, see below) with
    the recorded status code.

    A body the HAR recorded under a non-JSON content type (``text/plain``,
    ``application/xml``, ...) -- or one that only a lax parser accepts, see
    ``_has_non_finite_constant`` -- goes out through ``Response`` verbatim.
    Returning it as a Python string made FastAPI JSON-encode it -- a
    recorded ``plain text`` was served as ``"plain text"`` -- and forced
    the content-type to ``application/json``, so a client parsing the
    recorded type could no longer read the response at all.

    Replayable headers (``Location``, ``Set-Cookie``, ``ETag``, ...) are
    attached only when present, so an endpoint whose HAR carried none of them
    keeps emitting exactly the code it did before.

    A header name that repeats is the one case that needs more than one
    statement: ``Response(headers=...)`` takes a mapping, and Starlette
    rejects a mapping whose value is a list. A login that set a session
    cookie and a csrf cookie therefore replayed one of them, so the response
    is built first and the further values appended.
    """
    pairs = _replayable_header_pairs(headers, header_pairs)
    unique: dict[str, str] = {}
    repeats: list[tuple[str, str]] = []
    for name, value in pairs:
        if name in unique:
            repeats.append((name, value))
        else:
            unique[name] = value

    header_arg = f", headers={_py_literal(unique)}" if unique else ""

    if not _is_json_content_type(content_type) or _has_non_finite_constant(body_text):
        media = content_type or "text/plain"
        # status_code leads the call so cli.stats' regex can read it, the
        # same way it reads JSONResponse(status_code=...).
        args: list[str] = []
        if status != 200:
            args.append(f"status_code={status}")
        args.append(f"content={json.dumps(body_text, ensure_ascii=False)}")
        args.append(f"media_type={json.dumps(media, ensure_ascii=False)}")
        return _response_statements(
            f"Response({', '.join(args)}{header_arg})", repeats, indent
        )

    body_expr = body_literal(body_text)
    if status == 200 and not unique and not repeats:
        return f"{indent}return {body_expr}"
    status_arg = f"status_code={status}, " if status != 200 else ""
    return _response_statements(
        f"JSONResponse({status_arg}content={body_expr}{header_arg})", repeats, indent
    )


def _response_statements(
    construction: str, repeats: list[tuple[str, str]], indent: str
) -> str:
    """A return statement, plus an append per repeated header value.

    ``_response`` rather than ``response`` so the name cannot collide with a
    query parameter of the same spelling.
    """
    if not repeats:
        return f"{indent}return {construction}"

    lines = [f"{indent}_response = {construction}"]
    for name, value in repeats:
        lines.append(
            f"{indent}_response.headers.append("
            f"{json.dumps(name)}, {json.dumps(value, ensure_ascii=False)})"
        )
    lines.append(f"{indent}return _response")
    return "\n".join(lines)


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

    The path is a recorded value, not source. A capture whose URL carried
    ``%22`` decodes to a quote, and interpolating it raw produced
    ``@app.get("/api/a"b")`` -- an unterminated string literal that took the
    whole generated module down. A backslash was quieter and worse: ``\\b``
    is the backspace escape, so the decorator compiled and the route then
    matched nothing.
    """
    path_literal = json.dumps(path, ensure_ascii=False)
    if method in _APP_VERBS:
        return f'@app.{method.lower()}({path_literal})'
    method_literal = json.dumps(method, ensure_ascii=False)
    return f'@app.api_route({path_literal}, methods=[{method_literal}])'


_PATH_PARAM_RE = re.compile(r"\{([^{}:/]+)\}")


def _path_params(path: str) -> list[str]:
    """Extract ``{name}`` placeholders from a route path, in order.

    ``/api/user/{id}/orders/{order_id}`` yields ``["id", "order_id"]``.
    Empty braces, names containing ``/`` or ``:`` (OpenAPI style params
    like ``{id:min=1}``) are skipped rather than emitted as broken args.
    """
    return [m.group(1).strip() for m in _PATH_PARAM_RE.finditer(path) if m.group(1).strip()]


def _arg_signature(path: str, query_params: dict[str, Any] | None) -> list[str]:
    """Build the function-argument list for a route handler.

    Path placeholders come first (FastAPI binds them positionally from the
    decorator path), then query parameters. The URL always supplies a value
    for a path placeholder, so plain ones are declared required (``id:
    str``) -- a made-up default would never be used and FastAPI rejects
    ``Path("x")`` with "cannot have a default value". A placeholder that is
    not a valid identifier (``{user-id}``) or collides with a module-level
    name (``{status}``) is renamed via ``_safe_param_name`` and rebound to
    the original key through ``Path(..., alias=...)``.

    Query parameters keep their recorded value as the default so one
    handler can serve *all* recorded scenarios without FastAPI rejecting a
    request that omits a key a later branch might test.

    Every emitted argument must also have a *distinct* name. A recorded
    query key can sanitize onto a path placeholder (``/users/{id}?id=7``) or
    onto another query key (``?a b=1&a-b=2``), and Python rejects the
    duplicate outright ("duplicate argument 'id' in function definition"),
    so the whole mock file failed to import over one such key. A name that
    is already taken is suffixed and rebound through ``alias=`` so it still
    binds to the key the HAR recorded.
    """
    return _arg_signature_with_names(path, query_params)[0]


def _arg_signature_with_names(
    path: str,
    query_params: dict[str, Any] | None,
) -> tuple[list[str], dict[str, str]]:
    """``_arg_signature`` plus the key -> declared-argument-name map.

    The name map is what lets a conditional branch test the parameter the
    signature actually declared. When a query key and a path placeholder
    share a name, ``_arg_signature`` renames the query one (``id`` ->
    ``id_2``); a branch written against the raw key would then read the
    path segment instead of the recorded query value.
    """
    used: set[str] = set()
    required: list[str] = []
    defaulted: list[str] = []
    renamed: dict[str, str] = {}

    def _claim(name: str) -> str:
        candidate, suffix = name, 2
        while candidate in used:
            candidate = f"{name}_{suffix}"
            suffix += 1
        used.add(candidate)
        return candidate

    for name in _path_params(path):
        safe = _claim(_safe_param_name(name))
        if safe == name:
            required.append(f"{safe}: str")
        else:
            defaulted.append(f"{safe}: str = Path(..., alias={json.dumps(name)})")

    if query_params:
        for param, default_val in query_params.items():
            safe = _claim(_safe_param_name(param))
            renamed[param] = safe
            # json.dumps handles quotes/backslashes/newlines inside the value;
            # a plain f-string interpolation would emit broken Python.
            default_literal = json.dumps(str(default_val))
            if safe == param:
                defaulted.append(f"{safe}: str = {default_literal}")
            else:
                # FastAPI binds a query parameter on the argument name, so a
                # sanitized name would never match the key the HAR recorded:
                # "user-id" has to stay reachable as user-id, not user_id.
                defaulted.append(
                    f"{safe}: str = Query({default_literal}, "
                    f"alias={json.dumps(param, ensure_ascii=False)})"
                )

    # A renamed placeholder carries a default, and Python forbids a defaulted
    # parameter ahead of a required one, so the plain ones lead.
    return required + defaulted, renamed


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

    sample_query_params = (
        (sample_request or {}).get("query_params") or {}
    )

    has_query_params = bool(sample_query_params)

    if use_smart_fallback and method in ["POST", "PUT", "PATCH", "DELETE"] and has_request_body:
        return _generate_smart_route(method, path, all_responses, func_name, latency_ms)

    if use_smart_fallback and method == "GET" and has_query_params and len(all_responses) > 1:
        return _generate_query_route(method, path, all_responses, func_name, sample_request, latency_ms)

    if not all_responses:
        sig = ", ".join(_arg_signature(path, sample_query_params))
        return (
            _route_decorator(method, path) + "\n"
            f"async def {func_name}({sig}):\n"
            f'{_FB}"""Mock endpoint -- no HAR response data."""\n'
            f"{latency}"
            f"{_FB}return {{}}\n"
        )

    first_resp = all_responses[0]
    sc0 = first_resp.get("status") or 200
    body_code = _replay_line(
        sc0,
        first_resp.get("body") or "",
        first_resp.get("content_type"),
        first_resp.get("headers"),
        header_pairs=first_resp.get("header_pairs"),
    )

    # Path placeholders and recorded query keys become typed handler
    # arguments. Without them the OpenAPI schema advertises a bare endpoint
    # and clients cannot discover that /api/user/{id} takes an id.
    sig = ", ".join(_arg_signature(path, sample_query_params))

    if len(all_responses) > 1:
        # Captures from two origins that share a path land in one endpoint,
        # because the mock answers on a single origin. Naming the origin on
        # each scenario line keeps a surprising answer explainable: without it
        # "2 HAR scenarios recorded" hides that the default one came from a
        # host this endpoint was never about.
        origins = [
            urlparse(r.get("request", {}).get("url") or "").netloc
            for r in all_responses
        ]
        show_origins = len({origin for origin in origins if origin}) > 1

        lines = [
            _route_decorator(method, path),
            f"async def {func_name}({sig}):",
            f'{_FB}"""Mock endpoint -- {len(all_responses)} HAR scenarios recorded.',
        ]
        for i, resp in enumerate(all_responses, start=1):
            sc = resp.get("status") or 200
            preview = _docstring_safe((resp.get("body") or "")[:60])
            origin = origins[i - 1]
            from_origin = f" (from {origin})" if show_origins and origin else ""
            lines.append(f'{_FB}  [{i}] status {sc}: {preview}{from_origin}')
        lines.append(f'{_FB}"""')
        if latency:
            lines.append(latency.rstrip("\n"))
        lines.append(body_code)
        return "\n".join(lines) + "\n"

    return (
        _route_decorator(method, path) + "\n"
        f"async def {func_name}({sig}):\n"
        f'{_FB}"""Mock endpoint -- HAR status {sc0}."""\n'
        f"{latency}"
        f"{body_code}\n"
    )


def _dedupe_requests(
    parsed: list[tuple[Any, ...]],
) -> list[tuple[Any, ...]]:
    """Collapse duplicate request bodies, keeping the first response.

    Two entries with the same JSON body should route to one response, so a
    repeated body is dropped after the first occurrence. Entries are opaque
    tuples of at least ``(key_dict, status, body)``; the trailing elements
    (a content type, for the query router) ride along untouched.
    """
    seen: dict[str, tuple[Any, ...]] = {}
    for item in parsed:
        key = json.dumps(item[0], sort_keys=True)
        if key not in seen:
            seen[key] = item
    return list(seen.values())


def _select_discriminating_fields(
    distinct: list[tuple[Any, ...]],
    all_fields: list[str],
) -> list[str]:
    """Pick the smallest field set that separates every distinct response.

    Greedy: start with no fields, then keep adding the field that resolves
    the most remaining "different response, same key" collisions until no
    pair of distinct responses shares a key, or the fields run out. This is
    what lets routing work when a single field is not enough, e.g. requests
    that differ only on a secondary field like ``region`` while ``role``
    stays the same.

    Only positions 0-2 (key dict, status, body) are inspected, so callers may
    append extra fields (the recorded content type) without changing this.
    """
    n = len(distinct)
    resp_sig = [
        (item[1], json.dumps(item[2], sort_keys=True))
        for item in distinct
    ]

    def keys(fields: list[str]) -> list[tuple]:
        return [tuple(item[0].get(f) for f in fields) for item in distinct]

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

    # The raw body text, content type and headers ride along after the
    # discriminator fields (positions 0-2) so the replay line can emit them
    # unchanged instead of re-serialising a parsed copy.
    parsed_requests: list[tuple[Any, ...]] = []

    for resp in all_responses:
        req_body = resp.get("request", {}).get("body", "")
        resp_status = resp.get("status") or 200
        resp_body = resp.get("body", "")

        if req_body:
            try:
                req_data = json.loads(req_body) if isinstance(req_body, str) else req_body
                resp_data = json.loads(resp_body) if isinstance(resp_body, str) else resp_body
                if isinstance(req_data, dict):
                    # resp_body is the recorded text the replay line emits; a
                    # caller may hand over an already-parsed object instead,
                    # in which case re-serialise it as the old code did.
                    raw_body = resp_body if isinstance(resp_body, str) else json.dumps(resp_data)
                    parsed_requests.append((
                        req_data, resp_status, resp_data,
                        raw_body, resp.get("content_type"), resp.get("headers"),
                        resp.get("header_pairs"),
                    ))
            except (json.JSONDecodeError, TypeError):
                continue

    distinct = _dedupe_requests(parsed_requests)

    if len(distinct) < 2:
        return build_route(method, path, all_responses, func_name, use_smart_fallback=False, latency_ms=latency_ms)

    all_fields: list[str] = []
    for item in distinct:
        for field in item[0]:
            if field not in all_fields:
                all_fields.append(field)

    fields = _select_discriminating_fields(distinct, all_fields)

    if not fields:
        return build_route(method, path, all_responses, func_name, use_smart_fallback=False, latency_ms=latency_ms)

    # Path placeholders must be declared even on body-routing handlers,
    # or FastAPI rejects requests with "no path params were defined".
    # ``request`` and the path args are all default-less, which keeps the
    # signature valid Python ahead of the defaulted query args.
    sig = ", ".join(_arg_signature(path, None))

    lines = [
        _route_decorator(method, path),
        f"async def {func_name}(request: Request, {sig}):" if sig
        else f"async def {func_name}(request: Request):",
        f'{_FB}"""Smart mock endpoint with conditional routing."""',
    ]
    if latency:
        lines.append(latency.rstrip("\n"))
    lines.append(f'{_FB}body = await request.json() if request.headers.get("content-type", "").startswith("application/json") else {{}}')
    lines.append("")

    emitted: set[str] = set()
    first = True
    for req_data, status, _resp_data, resp_body, resp_ct, resp_headers, resp_pairs in distinct:
        checks = [
            (
                # The key comes from a recorded request body, so it is data,
                # not source: a key holding a quote produced
                # `body.get("a"b")` and the module would not parse.
                f'body.get({json.dumps(field, ensure_ascii=False)}) == {_py_literal(req_data[field])}'
                if field in req_data
                else f'body.get({json.dumps(field, ensure_ascii=False)}) is None'
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

        lines.append(_replay_line(
            status, resp_body, resp_ct, resp_headers,
            header_pairs=resp_pairs, indent=_FB * 2,
        ))

    default_response = next(
        (resp for resp in all_responses if 200 <= (resp.get("status") or 200) < 300),
        all_responses[0]
    )
    default_resp = default_response.get("body") or "{}"
    default_status = default_response.get("status") or 200
    lines.append(f'{_FB}else:')
    lines.append(_replay_line(
        default_status,
        default_resp,
        default_response.get("content_type"),
        default_response.get("headers"),
        header_pairs=default_response.get("header_pairs"),
        indent=_FB * 2,
    ))

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
    "asyncio", "time", "json", "defaultdict", "app", "Query", "Path",
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
    distinct: list[tuple[Any, ...]] = []
    for resp in all_responses:
        qp = resp.get("request", {}).get("query_params", {})
        if qp:
            distinct.append((
                qp,
                resp.get("status") or 200,
                resp.get("body") or "{}",
                resp.get("content_type"),
                resp.get("headers"),
                resp.get("header_pairs"),
            ))

    distinct = _dedupe_requests(distinct)

    all_fields: list[str] = []
    for item in distinct:
        for field in item[0]:
            if field not in all_fields:
                all_fields.append(field)

    fields = _select_discriminating_fields(distinct, all_fields) if len(distinct) >= 2 else []

    # Declare the sampled params plus any key a branch might test. A later
    # response can carry query keys the sampled request did not, and a branch
    # referencing an undeclared name would NameError in the generated server.
    declared = dict(query_params)
    for field in all_fields:
        declared.setdefault(field, "")

    sig_list, param_names = _arg_signature_with_names(path, declared)
    sig = ", ".join(sig_list)

    lines = [
        _route_decorator(method, path),
        f"async def {func_name}({sig}):",
    ]

    if len(all_responses) > 1:
        lines.append(f'{_FB}"""Mock endpoint with query parameter support.')
        for i, resp in enumerate(all_responses, start=1):
            sc = resp.get("status") or 200
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
        for qp, status_, resp_body, resp_ct, resp_headers, resp_pairs in distinct:
            checks = [
                f'{param_names.get(field, _safe_param_name(field))} == {_py_literal(qp[field])}'
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

            lines.append(_replay_line(
                status_, resp_body, resp_ct, resp_headers,
                header_pairs=resp_pairs, indent=_FB * 2,
            ))

        default_response = next(
            (resp for resp in all_responses if 200 <= (resp.get("status") or 200) < 300),
            all_responses[0],
        )
        default_status = default_response.get("status") or 200
        lines.append(f'{_FB}else:')
        lines.append(_replay_line(
            default_status,
            default_response.get("body") or "{}",
            default_response.get("content_type"),
            default_response.get("headers"),
            header_pairs=default_response.get("header_pairs"),
            indent=_FB * 2,
        ))
    else:
        sc0 = all_responses[0].get("status") or 200
        lines.append(_replay_line(
            sc0,
            all_responses[0].get("body") or "{}",
            all_responses[0].get("content_type"),
            all_responses[0].get("headers"),
            header_pairs=all_responses[0].get("header_pairs"),
        ))

    return "\n".join(lines) + "\n"


def generate_func_name(method: str, path: str) -> str:
    """Build a valid Python function name from HTTP method and path."""
    name = method.lower() + "_" + path.replace("/", "_").replace("{", "").replace("}", "")
    name = re.sub(r'[^a-zA-Z0-9_]', '_', name)
    return "_".join(filter(None, name.split("_")))
