"""
MockClaw Traffic Parser
Parses HAR files and extracts API endpoints for mock generation.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


# Static asset MIME types to filter out
STATIC_MIME_TYPES = {
    'image/', 'css/', 'font/', 'application/javascript',
    'application/x-javascript', 'text/css', 'text/javascript',
    'text/html', 'video/', 'audio/'
}

# URL patterns to filter
STATIC_URL_PATTERNS = ['.js', '.css', '.png', '.jpg', '.jpeg', '.gif', '.svg', 
                       '.ico', '.woff', '.woff2', '.ttf', '.eot', '.webp']


@dataclass
class HTTPRequest:
    """Represents a parsed HTTP request."""
    url: str
    method: str
    headers: dict
    query_params: dict
    body: Optional[str] = None
    post_data: Optional[dict] = None


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
    resource_path: str  # e.g., /api/users/{id}
    base_path: str      # e.g., /api/users
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
        
        # Handle common ID patterns
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{uuid}', path, flags=re.IGNORECASE)
        path = re.sub(r'/[0-9]+', '/{id}', path)
        
        return path or '/'
    
    def _parse_headers(self, headers: list) -> dict:
        """Convert headers list to dictionary."""
        return {h['name'].lower(): h['value'] for h in headers}
    
    def _parse_query_params(self, query_string: str) -> dict:
        """Parse query string into dictionary."""
        if not query_string:
            return {}
        return {param['name']: param.get('value', '') 
                for param in query_string}
    
    def _parse_request(self, entry: dict) -> HTTPRequest:
        """Parse a HAR entry's request."""
        request = entry.get('request', {})
        url = request.get('url', '')
        
        # Parse query string
        query_params = request.get('queryString', [])
        query_dict = {p['name']: p.get('value', '') for p in query_params}
        
        # Parse body
        body = None
        post_data = None
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
            body=body,
            post_data=post_data
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
                # Extract base path (remove trailing /{param})
                base_path = re.sub(r'/\{[^}]+\}$', '', resource_path)
                endpoint_groups[endpoint_key] = APIEndpoint(
                    resource_path=resource_path,
                    base_path=base_path or resource_path,
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
                    # Export ALL responses so the generator can handle multiple
                    # scenarios (e.g. 200 OK and 400 Bad Request for the same URL).
                    "sample_responses": [
                        {
                            "status": r.status,
                            "headers": r.headers,
                            "body": r.body,
                            "content_type": r.content_type,
                        }
                        for r in ep.responses
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
