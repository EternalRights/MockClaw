"""
MockClaw Core — HAR Parser
===========================

Extracts, normalises and groups API endpoints from HTTP Archive (HAR) files.

Typical usage::

    parser = HARParser("traffic/recording.har")
    endpoints = parser.parse()           # List[APIEndpoint]
    summary   = parser.export_as_dict()  # dict for LLM consumption

The parser automatically:
- Skips static assets (JS, CSS, images, fonts).
- Normalises UUIDs and numeric IDs into ``{uuid}`` / ``{id}`` path segments.
- Groups requests by ``METHOD:path`` so duplicate calls are merged.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import urlparse


@dataclass
class HTTPRequest:
    """A single parsed HTTP request extracted from a HAR entry.

    Attributes:
        url: The full request URL (before normalisation).
        method: HTTP method (GET, POST, …).
        headers: Mapping of header names to values.
        query_params: Parsed query-string parameters.
        body: Raw request body, if present.
    """

    url: str
    method: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    body: Optional[str] = None


@dataclass
class HTTPResponse:
    """A single parsed HTTP response extracted from a HAR entry.

    Attributes:
        status: HTTP status code (e.g. 200, 404).
        headers: Mapping of header names to values.
        body: Raw response body text, if present.
        content_type: MIME type from the ``Content-Type`` header.
    """

    status: int
    headers: Dict[str, str]
    body: Optional[str] = None
    content_type: Optional[str] = None


@dataclass
class APIEndpoint:
    """A grouped API endpoint merging multiple request/response pairs.

    Attributes:
        resource_path: Normalised URL path (UUIDs/IDs replaced with placeholders).
        method: HTTP method.
        requests: All observed requests for this endpoint.
        responses: All observed responses for this endpoint.
    """

    resource_path: str
    method: str
    requests: List[HTTPRequest] = field(default_factory=list)
    responses: List[HTTPResponse] = field(default_factory=list)


class HARParser:
    """Parser for HAR (HTTP Archive) format files.

    Reads a ``.har`` file, extracts HTTP entries, filters out static
    assets, normalises dynamic path segments, and groups requests
    by ``METHOD:path``.

    Args:
        har_file_path: Path to the HAR file to parse.
    """

    def __init__(self, har_file_path: str) -> None:
        self.har_file_path: Path = Path(har_file_path)
        self.entries: List[dict] = []
        self.api_endpoints: List[APIEndpoint] = []

    def load_har(self) -> dict:
        """Load and deserialise the HAR file.

        Returns:
            The parsed JSON content of the HAR file.

        Raises:
            FileNotFoundError: If the HAR file does not exist.
            json.JSONDecodeError: If the file is not valid JSON.
        """
        with open(self.har_file_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def _extract_url_path(self, url: str) -> str:
        """Normalise a URL into a resource path with placeholder segments.

        Strips query strings, replaces UUIDs with ``{uuid}``, and replaces
        bare numeric segments with ``{id}``.

        Args:
            url: The full URL to normalise.

        Returns:
            The normalised path (e.g. ``/users/{uuid}/orders/{id}``).
        """
        parsed = urlparse(url.split("?")[0])
        path = parsed.path
        # Replace UUIDs and numeric IDs
        path = re.sub(
            r"/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}",
            "/{uuid}",
            path,
            flags=re.IGNORECASE,
        )
        path = re.sub(r"/\d+", "/{id}", path)
        return path or "/"

    def parse(self) -> List[APIEndpoint]:
        """Parse all HAR entries and group them by normalised resource path.

        Static assets (``.js``, ``.css``, ``.png``, etc.) are filtered out
        automatically.

        Returns:
            A list of :class:`APIEndpoint` objects, one per unique
            ``METHOD:path`` combination found in the HAR data.
        """
        if not self.entries:
            har_data = self.load_har()
            self.entries = har_data.get("log", {}).get("entries", [])

        endpoint_groups: Dict[str, APIEndpoint] = {}

        for entry in self.entries:
            request = entry.get("request", {})
            response = entry.get("response", {})

            # Skip static assets — they are not API endpoints
            url = request.get("url", "")
            skip_extensions = (
                ".js",
                ".css",
                ".png",
                ".jpg",
                ".gif",
                ".svg",
                ".ico",
                ".woff",
            )
            if any(ext in url.lower() for ext in skip_extensions):
                continue

            resource_path = self._extract_url_path(url)
            method = request.get("method", "GET")
            endpoint_key = f"{method}:{resource_path}"

            if endpoint_key not in endpoint_groups:
                endpoint_groups[endpoint_key] = APIEndpoint(
                    resource_path=resource_path,
                    method=method,
                )

            # Parse request headers, query params, and body
            req = HTTPRequest(
                url=url,
                method=method,
                headers={h["name"]: h["value"] for h in request.get("headers", [])},
                query_params={
                    q["name"]: q.get("value", "")
                    for q in request.get("queryString", [])
                },
                body=(
                    request.get("postData", {}).get("text")
                    if request.get("postData")
                    else None
                ),
            )

            # Parse response status, headers, and body
            resp = HTTPResponse(
                status=response.get("status", 200),
                headers={h["name"]: h["value"] for h in response.get("headers", [])},
                body=response.get("content", {}).get("text"),
                content_type=response.get("content", {}).get("mimeType"),
            )

            endpoint_groups[endpoint_key].requests.append(req)
            endpoint_groups[endpoint_key].responses.append(resp)

        self.api_endpoints = list(endpoint_groups.values())
        return self.api_endpoints

    def export_as_dict(self) -> dict:
        """Export parsed endpoints as a plain dictionary.

        Designed for LLM consumption — each endpoint includes the first
        observed request URL/body and response status/body as samples.

        Returns:
            A dictionary with ``total_endpoints`` count and an ``endpoints``
            list of sample data per endpoint.

        Raises:
            ValueError: If no HAR data has been parsed yet.
        """
        if not self.api_endpoints:
            self.parse()
        return {
            "total_endpoints": len(self.api_endpoints),
            "endpoints": [
                {
                    "resource_path": ep.resource_path,
                    "method": ep.method,
                    "sample_request": {
                        "url": ep.requests[0].url if ep.requests else "",
                        "body": ep.requests[0].body if ep.requests else None,
                    },
                    "sample_response": {
                        "status": ep.responses[0].status if ep.responses else 200,
                        "body": ep.responses[0].body if ep.responses else None,
                    },
                }
                for ep in self.api_endpoints
            ],
        }
