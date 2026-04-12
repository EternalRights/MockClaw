"""
MockClaw Traffic Parser
Parses HAR files and extracts API endpoints for mock generation.
"""

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# JSON import - keep stdlib for file I/O (orjson doesn't support file objects)
import json


# Static asset MIME types to filter out
STATIC_MIME_TYPES = {
    'image/', 'css/', 'font/', 'application/javascript',
    'application/x-javascript', 'text/css', 'text/javascript',
    'text/html', 'video/', 'audio/'
}

# URL patterns to filter
STATIC_URL_PATTERNS = ['.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', 
                       '.ico', '.woff', '.woff2', '.ttf', '.eot', '.webp']

# Pre-compiled regex patterns for URL path extraction (performance optimization)
UUID_PATTERN = re.compile(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE)
ID_PATTERN = re.compile(r'/[0-9]+')


@dataclass
class HTTPRequest:
    """Represents a parsed HTTP request."""
    url: str
    method: str
    headers: dict
    query_params: dict
    body: Optional[str] = None


@dataclass
class HTTPResponse:
    """Represents a parsed HTTP response."""
    status: int
    headers: dict
    body: Optional[str] = None
    content_type: Optional[str] = None


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
        """Initialize the HAR parser.

        Args:
            har_file_path: Path to the HAR file to parse.
        """
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
        
        # Check URL patterns
        for pattern in STATIC_URL_PATTERNS:
            if url.lower().endswith(pattern):
                return True
        
        # Check MIME type in response
        response = entry.get('response', {})
        content = response.get('content', {})
        mime_type = content.get('mimeType', '').lower()
        
        for static_prefix in STATIC_MIME_TYPES:
            if mime_type.startswith(static_prefix):
                return True
        
        return False
    
    def _extract_url_path(self, url: str) -> str:
        """Extract the path from a URL, replacing dynamic segments."""
        from urllib.parse import urlparse
        
        # Remove query string first
        clean_url = url.split('?')[0]
        
        # Parse URL to extract path
        parsed = urlparse(clean_url)
        path = parsed.path
        
        # Handle common ID patterns (using pre-compiled regex)
        path = UUID_PATTERN.sub('/{uuid}', path)
        path = ID_PATTERN.sub('/{id}', path)
        
        return path or '/'
    
    def _parse_headers(self, headers: list) -> dict:
        """Convert headers list to dictionary."""
        return {h['name'].lower(): h['value'] for h in headers}
    
    def _parse_request(self, entry: dict) -> HTTPRequest:
        """Parse a HAR entry's request."""
        request = entry.get('request', {})
        url = request.get('url', '')
        
        # Parse query string
        query_params = request.get('queryString', [])
        query_dict = {p['name']: p.get('value', '') for p in query_params}
        
        # Parse body
        body = None
        if request.get('postData'):
            post_data = request['postData']
            if post_data.get('mimeType') == 'application/json':
                try:
                    body = post_data.get('text', '')
                except Exception:
                    body = str(post_data)
        
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
            if header['name'].lower() == 'content-type':
                content_type = header['value']
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
        
        # Group entries by resource path
        endpoint_groups: dict[str, APIEndpoint] = {}
        
        for entry in self.entries:
            if self._is_static_asset(entry):
                continue
            
            request = self._parse_request(entry)
            response = self._parse_response(entry)
            resource_path = self._extract_url_path(request.url)
            
            # Create endpoint key
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
        """Export parsed data as dictionary for LLM consumption.

        For each endpoint, exports the first request and ALL observed responses
        (not just the first one), so the generator can produce routes with
        conditional branches for different scenarios.
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
                    # Export ALL responses with their corresponding requests
                    # so the generator can handle multiple scenarios (e.g. 200 OK and 400 Bad Request).
                    # Each response includes the request that triggered it for smart routing.
                    "sample_responses": [
                        {
                            "status": r.status,
                            "headers": r.headers,
                            "body": r.body,
                            "content_type": r.content_type,
                            # Include request body for smart fallback routing
                            "request": {
                                "body": ep.requests[i].body if i < len(ep.requests) and ep.requests[i].body else None,
                            } if ep.requests else None,
                        }
                        for i, r in enumerate(ep.responses)
                    ],
                    # Keep first response as default for backward compat.
                    "sample_response": {
                        "status": ep.responses[0].status if ep.responses else 200,
                        "headers": ep.responses[0].headers if ep.responses else {},
                        "body": ep.responses[0].body if ep.responses else None,
                        "content_type": ep.responses[0].content_type if ep.responses else None,
                    },
                }
                for ep in endpoints
            ],
        }


def main():
    """CLI entry point for testing."""
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python parser.py <path_to_har_file>")
        sys.exit(1)
    
    parser = HARParser(sys.argv[1])
    endpoints = parser.parse()
    
    print(f"Parsed {len(endpoints)} API endpoints:")
    for ep in endpoints:
        print(f"  - {ep.endpoint_id}")


if __name__ == "__main__":
    main()
