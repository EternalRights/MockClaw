"""
MockClaw Traffic Parser
Parses HAR files and extracts API endpoints for mock generation.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlparse

import json


STATIC_MIME_PREFIXES = (
    'image/', 'css/', 'font/', 'application/javascript',
    'application/x-javascript', 'text/css', 'text/javascript',
    'text/html', 'video/', 'audio/'
)

STATIC_URL_EXTENSIONS = frozenset([
    '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg',
    '.ico', '.woff', '.woff2', '.ttf', '.eot', '.webp', '.map',
])

UUID_PATTERN = re.compile(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)
ID_PATTERN = re.compile(r'/[0-9]+(?=/|$)')


def _unique_placeholders(pattern: re.Pattern, path: str, base: str) -> str:
    """Replace matches with ``{base}``, ``{base_2}``, ``{base_3}``, ...

    Naming one parameter twice is fatal twice over: Starlette refuses the
    path outright ("Duplicated param name id"), and the generated handler
    would declare the same argument twice, so the whole mock file failed to
    import. The ordinary nested-resource capture /users/1/orders/2 collapsed
    both numbered segments to ``{id}`` and hit exactly that. The first match
    keeps the plain name, leaving single-segment paths byte-identical.
    """
    seen = 0

    def replace(_match: re.Match) -> str:
        nonlocal seen
        seen += 1
        return f"/{{{base}}}" if seen == 1 else f"/{{{base}_{seen}}}"

    return pattern.sub(replace, path)

# RFC 7230 token characters: what a request method may legally consist of.
# Kept in sync with brain's EndpointInfo validator so both layers reject the
# same set of junk methods.
METHOD_TOKEN_PATTERN = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")


def _normalize_method(value: object) -> str:
    """Canonicalize an HTTP method coming out of a HAR file.

    Not every exporter writes ``GET``; hand-edited and tool-generated
    archives turn up as ``get`` or ``Get``. Everything downstream -- endpoint
    grouping, the smart-router guards, the function-name builder -- assumes
    the upper-case spelling, so a lower-case method silently loses conditional
    routing and splits one resource into two duplicate routes.

    A method that violates the RFC 7230 token rule (embedded spaces,
    slashes, parens: "GET WITH SPACE", "GET/POST") is not something a real
    client can send, and brain's response schema rejects it entry-by-entry.
    Falling back to GET here keeps CLI-generated mocks importable instead
    of registering ``api_route(methods=["GET WITH SPACE"])`` routes no
    request can ever reach. Token-shaped methods -- PROPFIND, MKCOL, "123" --
    pass through untouched.
    """
    method = str(value).strip().upper() if value else ''
    if method and not METHOD_TOKEN_PATTERN.match(method):
        return 'GET'
    return method or 'GET'


def _to_int(value: object, default: int) -> int:
    """Coerce a HAR value to int, tolerating null, blank and junk.

    Exporters write ``null`` (or "") for fields the spec marks required.
    ``int(None)`` raises TypeError and takes the whole file down with it, and
    a null status silently propagates into the generated server instead of
    falling back to 200.
    """
    if value is None or value == "":
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_str(value: object, default: str = "") -> str:
    """Coerce a HAR field to str, treating null as absent.

    ``dict.get(k, "")`` only falls back when the *key* is missing. Exporters
    (Chrome among them) emit ``"value": null`` for query and header entries
    they could not resolve, and the Python ``None`` then travels the whole
    pipeline: a null query value became ``q: str = "None"`` in the generated
    handler plus an unreachable ``if q == None`` branch that silently served
    the wrong recorded scenario. A null URL crashed the parse inside
    ``urlparse``. Treat null like an absent field and stringify non-string
    scalars, since HAR fields are strings on the wire.
    """
    if value is None:
        return default
    return value if isinstance(value, str) else str(value)


def _as_mapping(value: object) -> dict:
    """Return *value* when it is an object, else an empty dict.

    ``headers``, ``queryString`` and ``entries`` are arrays of objects per
    the HAR spec, but hand-edited archives carry a bare string or null where
    an object belongs. Indexing into the raw item raised AttributeError and
    aborted the entire parse.
    """
    return value if isinstance(value, dict) else {}


@dataclass
class HTTPRequest:
    """Represents a parsed HTTP request."""
    url: str
    method: str
    headers: dict
    query_params: dict
    body: str | None = None


@dataclass
class HTTPResponse:
    """Represents a parsed HTTP response."""
    status: int
    headers: dict
    body: str | None = None
    content_type: str | None = None
    latency_ms: int = 0
    # The same headers in recorded order, with repeats kept. ``headers`` is
    # the lossy view the dashboard and the JSON API have always exposed; this
    # is what the generated route replays, so a repeated Set-Cookie survives.
    header_pairs: list[tuple[str, str]] = field(default_factory=list)


@dataclass
class APIEndpoint:
    """Represents a grouped API endpoint resource."""
    resource_path: str
    method: str
    requests: list[HTTPRequest] = field(default_factory=list)
    responses: list[HTTPResponse] = field(default_factory=list)

    @property
    def endpoint_id(self) -> str:
        """Unique identifier for this endpoint."""
        return f"{self.method.upper()} {self.resource_path}"


class HARParser:
    """Parser for HAR (HTTP Archive) format files."""

    def __init__(self, har_file_path: str):
        self.har_file_path = Path(har_file_path)
        self.entries: list[dict] = []
        self.api_endpoints: list[APIEndpoint] = []

    def load_har(self) -> dict:
        """Load and parse the HAR file."""
        with open(self.har_file_path, 'r', encoding='utf-8') as f:
            har_data = json.load(f)
        if not isinstance(har_data, dict):
            har_data = {}
        entries = _as_mapping(har_data.get('log')).get('entries')
        # A hand-edited file may write a bare string or object where the
        # entries array belongs; iterating that would walk characters or keys.
        self.entries = entries if isinstance(entries, list) else []
        return har_data

    def _is_static_asset(self, entry: dict) -> bool:
        """Check if the entry is a static asset to filter out."""
        request = _as_mapping(entry.get('request'))
        url = _to_str(request.get('url'))

        # Parse the path out of the URL before taking the extension so that
        # query strings (e.g. /app.js?ver=1) and scheme/host don't break the
        # extension check.
        parsed = urlparse(url)
        _, ext = os.path.splitext(parsed.path.lower())
        if ext in STATIC_URL_EXTENSIONS:
            return True

        response = _as_mapping(entry.get('response'))
        content = _as_mapping(response.get('content'))
        mime_type = _to_str(content.get('mimeType')).lower()

        for prefix in STATIC_MIME_PREFIXES:
            if mime_type.startswith(prefix):
                return True

        return False

    def _extract_url_path(self, url: str) -> str:
        """Extract the path from a URL, replacing dynamic segments."""
        clean_url = url.split('?')[0]
        parsed = urlparse(clean_url)
        # A HAR records the URL as it went on the wire, so non-ASCII and
        # reserved octets arrive percent-encoded (browsers always encode a
        # CJK path). The generated route is matched against the path the
        # server has already decoded, so emitting the encoded form produced a
        # route nothing could reach: a capture of /api/%E7%94%A8%E6%88%B7/1
        # mocked 404 for the very request it recorded. unquote, not
        # unquote_plus -- '+' is a literal character in a path, not a space.
        path = unquote(parsed.path)
        path = _unique_placeholders(UUID_PATTERN, path, 'uuid')
        path = _unique_placeholders(ID_PATTERN, path, 'id')
        return path or '/'

    def _parse_header_pairs(self, headers: list | None) -> list[tuple[str, str]]:
        """Header name/value pairs in recorded order, duplicates kept.

        The HAR spec allows one name more than once; Set-Cookie is the case
        that matters, and collapsing into a dict kept only the last one -- a
        login that set a session cookie and a csrf cookie replayed one of
        them. Names are lowercased the way ``_parse_headers`` has always done.
        """
        pairs: list[tuple[str, str]] = []
        for h in headers or []:
            h = _as_mapping(h)
            name = h.get('name')
            if name:
                pairs.append((str(name).lower(), _to_str(h.get('value'))))
        return pairs

    def _parse_headers(self, headers: list | None) -> dict:
        """Convert headers list to dictionary."""
        return dict(self._parse_header_pairs(headers))

    def _parse_request(self, entry: dict) -> HTTPRequest:
        """Parse a HAR entry's request."""
        request = _as_mapping(entry.get('request'))
        url = _to_str(request.get('url'))

        # The URL is what the client actually asked for, and it carries the
        # query on its own. queryString is a convenience: browsers fill it in,
        # but hand-written and some non-browser HARs leave it empty, and a
        # capture of /products?category=books then produced a mock with no
        # query parameters at all -- every variant was answered with the first
        # recorded response. Start from the URL; queryString overrides it.
        query_dict: dict[str, str] = {}
        for name, value in parse_qsl(urlparse(url).query, keep_blank_values=True):
            query_dict[name] = value

        for p in request.get('queryString') or []:
            p = _as_mapping(p)
            name = p.get('name')
            if name:
                query_dict[str(name)] = _to_str(p.get('value'))

        body = None
        if request.get('postData'):
            post_data = _as_mapping(request['postData'])
            # HAR mimeType can carry parameters (e.g. "application/json;
            # charset=utf-8"); a plain equality check would drop the body.
            mime_type = _to_str(post_data.get('mimeType')).split(';')[0].strip().lower()
            if mime_type == 'application/json':
                body = _to_str(post_data.get('text'))

        return HTTPRequest(
            url=url,
            method=_normalize_method(request.get('method')),
            headers=self._parse_headers(request.get('headers', [])),
            query_params=query_dict,
            body=body
        )

    def _parse_response(self, entry: dict) -> HTTPResponse:
        """Parse a HAR entry's response."""
        response = _as_mapping(entry.get('response'))
        content = _as_mapping(response.get('content'))

        content_type = None
        for header in response.get('headers') or []:
            header = _as_mapping(header)
            if _to_str(header.get('name')).lower() == 'content-type':
                content_type = _to_str(header.get('value'))
                break

        if not content_type:
            # Chrome and friends record the type in content.mimeType and a
            # HAR may omit response headers entirely. Without this fallback
            # the mock has no type to replay the body under, so it forces
            # every response out as application/json.
            content_type = _to_str(content.get('mimeType')) or None

        return HTTPResponse(
            status=_to_int(response.get('status'), 200),
            headers=self._parse_headers(response.get('headers', [])),
            body=_to_str(content.get('text')) or None,
            content_type=content_type,
            latency_ms=_to_int(entry.get('time'), 0),
            header_pairs=self._parse_header_pairs(response.get('headers', [])),
        )

    def parse(self) -> list[APIEndpoint]:
        """Parse all entries and group by resource.

        Duplicate entries (same method, URL, request body, status and
        response body) are collapsed to one. Browser captures routinely
        contain repeats from polling, retries or page reloads, and keeping
        them inflates scenario counts and misleads the routing analyzer.
        """
        if not self.entries:
            self.load_har()

        endpoint_groups: dict[str, APIEndpoint] = {}
        seen: set[tuple] = set()

        for entry in self.entries:
            # A null or bare-string item in the entries array is not an
            # entry at all; coercing it to {} would fabricate a bogus "GET /"
            # endpoint, so drop it outright.
            if not isinstance(entry, dict):
                continue
            if self._is_static_asset(entry):
                continue

            request = self._parse_request(entry)
            response = self._parse_response(entry)
            resource_path = self._extract_url_path(request.url)

            signature = (
                request.method,
                request.url,
                request.body,
                response.status,
                response.body,
            )
            if signature in seen:
                continue
            seen.add(signature)

            endpoint_key = f"{request.method}:{resource_path}"

            if endpoint_key not in endpoint_groups:
                endpoint_groups[endpoint_key] = APIEndpoint(
                    resource_path=resource_path,
                    method=request.method
                )

            endpoint_groups[endpoint_key].requests.append(request)
            endpoint_groups[endpoint_key].responses.append(response)

        self.api_endpoints = list(endpoint_groups.values())
        return self.api_endpoints

    def get_endpoints(self) -> list[APIEndpoint]:
        """Get parsed endpoints."""
        if not self.api_endpoints:
            self.parse()
        return self.api_endpoints

    def export_as_dict(self) -> dict:
        """Export parsed data as dictionary for mock generation.

        For each endpoint, exports the first request and ALL observed responses
        so the generator can produce routes with conditional branches.
        """
        endpoints = self.get_endpoints()
        return {
            "total_endpoints": len(endpoints),
            "endpoints": [
                {
                    "resource_path": ep.resource_path,
                    "method": ep.method,
                    "avg_latency_ms": int(
                        sum(r.latency_ms for r in ep.responses) / len(ep.responses)
                    ) if ep.responses else 0,
                    "sample_request": {
                        "url": ep.requests[0].url if ep.requests else "",
                        "headers": ep.requests[0].headers if ep.requests else {},
                        "body": ep.requests[0].body if ep.requests else None,
                        "query_params": ep.requests[0].query_params if ep.requests else {},
                    },
                    "sample_responses": [
                        {
                            "status": r.status,
                            "headers": r.headers,
                            "header_pairs": [list(pair) for pair in r.header_pairs],
                            "body": r.body,
                            "content_type": r.content_type,
                            "request": {
                                "body": ep.requests[i].body if i < len(ep.requests) and ep.requests[i].body else None,
                                "query_params": ep.requests[i].query_params if i < len(ep.requests) else {},
                            } if ep.requests else None,
                        }
                        for i, r in enumerate(ep.responses)
                    ],
                }
                for ep in endpoints
            ],
        }
