"""
MockClaw Traffic Parser
Parses HAR files and extracts API endpoints for mock generation.
"""

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

import json


STATIC_MIME_PREFIXES = (
    'image/', 'css/', 'font/', 'application/javascript',
    'application/x-javascript', 'text/css', 'text/javascript',
    'text/html', 'video/', 'audio/'
)

STATIC_URL_EXTENSIONS = frozenset([
    '.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg',
    '.ico', '.woff', '.woff2', '.ttf', '.eot', '.webp'
])

UUID_PATTERN = re.compile(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)
ID_PATTERN = re.compile(r'/[0-9]+(?=/|$)')


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
        self.entries = har_data.get('log', {}).get('entries', [])
        return har_data

    def _is_static_asset(self, entry: dict) -> bool:
        """Check if the entry is a static asset to filter out."""
        request = entry.get('request', {})
        url = request.get('url', '')

        _, ext = os.path.splitext(url.lower())
        if ext in STATIC_URL_EXTENSIONS:
            return True

        response = entry.get('response', {})
        content = response.get('content', {})
        mime_type = content.get('mimeType', '').lower()

        for prefix in STATIC_MIME_PREFIXES:
            if mime_type.startswith(prefix):
                return True

        return False

    def _extract_url_path(self, url: str) -> str:
        """Extract the path from a URL, replacing dynamic segments."""
        clean_url = url.split('?')[0]
        parsed = urlparse(clean_url)
        path = parsed.path
        path = UUID_PATTERN.sub('/{uuid}', path)
        path = ID_PATTERN.sub('/{id}', path)
        return path or '/'

    def _parse_headers(self, headers: list) -> dict:
        """Convert headers list to dictionary."""
        result = {}
        for h in headers:
            name = h.get('name')
            if name:
                result[name.lower()] = h.get('value', '')
        return result

    def _parse_request(self, entry: dict) -> HTTPRequest:
        """Parse a HAR entry's request."""
        request = entry.get('request', {})
        url = request.get('url', '')

        query_params = request.get('queryString', [])
        query_dict = {}
        for p in query_params:
            name = p.get('name')
            if name:
                query_dict[name] = p.get('value', '')

        body = None
        if request.get('postData'):
            post_data = request['postData']
            if post_data.get('mimeType') == 'application/json':
                body = post_data.get('text', '')

        return HTTPRequest(
            url=url,
            method=request.get('method', 'GET'),
            headers=self._parse_headers(request.get('headers', [])),
            query_params=query_dict,
            body=body
        )

    def _parse_response(self, entry: dict) -> HTTPResponse:
        """Parse a HAR entry's response."""
        response = entry.get('response', {})
        content = response.get('content', {})

        content_type = None
        for header in response.get('headers', []):
            if header.get('name', '').lower() == 'content-type':
                content_type = header.get('value')
                break

        return HTTPResponse(
            status=response.get('status', 200),
            headers=self._parse_headers(response.get('headers', [])),
            body=content.get('text'),
            content_type=content_type
        )

    def parse(self) -> list[APIEndpoint]:
        """Parse all entries and group by resource."""
        if not self.entries:
            self.load_har()

        endpoint_groups: dict[str, APIEndpoint] = {}

        for entry in self.entries:
            if self._is_static_asset(entry):
                continue

            request = self._parse_request(entry)
            response = self._parse_response(entry)
            resource_path = self._extract_url_path(request.url)

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
                            "body": r.body,
                            "content_type": r.content_type,
                            "request": {
                                "body": ep.requests[i].body if i < len(ep.requests) and ep.requests[i].body else None,
                            } if ep.requests else None,
                        }
                        for i, r in enumerate(ep.responses)
                    ],
                }
                for ep in endpoints
            ],
        }
