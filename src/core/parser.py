"""
MockClaw Core - HAR Parser
Extracts API endpoints from HTTP Archive files.
"""

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, List, Dict
from urllib.parse import urlparse


@dataclass
class HTTPRequest:
    """Represents a parsed HTTP request."""
    url: str
    method: str
    headers: Dict[str, str]
    query_params: Dict[str, str]
    body: Optional[str] = None


@dataclass
class HTTPResponse:
    """Represents a parsed HTTP response."""
    status: int
    headers: Dict[str, str]
    body: Optional[str] = None
    content_type: Optional[str] = None


@dataclass
class APIEndpoint:
    """Represents a grouped API endpoint."""
    resource_path: str
    method: str
    requests: List[HTTPRequest] = field(default_factory=list)
    responses: List[HTTPResponse] = field(default_factory=list)


class HARParser:
    """Parser for HAR (HTTP Archive) format files."""
    
    def __init__(self, har_file_path: str):
        self.har_file_path = Path(har_file_path)
        self.entries: List[dict] = []
        self.api_endpoints: List[APIEndpoint] = []
        
    def load_har(self) -> dict:
        """Load and parse the HAR file."""
        with open(self.har_file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    def _extract_url_path(self, url: str) -> str:
        """Extract path from URL, normalizing dynamic segments."""
        parsed = urlparse(url.split('?')[0])
        path = parsed.path
        # Replace UUIDs and numeric IDs
        path = re.sub(r'/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '/{uuid}', path, flags=re.IGNORECASE)
        path = re.sub(r'/\d+', '/{id}', path)
        return path or '/'
    
    def parse(self) -> List[APIEndpoint]:
        """Parse all entries and group by resource."""
        if not self.entries:
            har_data = self.load_har()
            self.entries = har_data.get('log', {}).get('entries', [])
        
        endpoint_groups: Dict[str, APIEndpoint] = {}
        
        for entry in self.entries:
            request = entry.get('request', {})
            response = entry.get('response', {})
            
            # Skip static assets
            url = request.get('url', '')
            if any(ext in url.lower() for ext in ['.js', '.css', '.png', '.jpg', '.gif', '.svg', '.ico', '.woff']):
                continue
            
            resource_path = self._extract_url_path(url)
            method = request.get('method', 'GET')
            endpoint_key = f"{method}:{resource_path}"
            
            if endpoint_key not in endpoint_groups:
                endpoint_groups[endpoint_key] = APIEndpoint(
                    resource_path=resource_path,
                    method=method
                )
            
            # Parse request
            req = HTTPRequest(
                url=url,
                method=method,
                headers={h['name']: h['value'] for h in request.get('headers', [])},
                query_params={q['name']: q.get('value', '') for q in request.get('queryString', [])},
                body=request.get('postData', {}).get('text') if request.get('postData') else None
            )
            
            # Parse response
            resp = HTTPResponse(
                status=response.get('status', 200),
                headers={h['name']: h['value'] for h in response.get('headers', [])},
                body=response.get('content', {}).get('text'),
                content_type=response.get('content', {}).get('mimeType')
            )
            
            endpoint_groups[endpoint_key].requests.append(req)
            endpoint_groups[endpoint_key].responses.append(resp)
        
        self.api_endpoints = list(endpoint_groups.values())
        return self.api_endpoints
    
    def export_as_dict(self) -> dict:
        """Export parsed data as dictionary for LLM consumption."""
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
                        "body": ep.requests[0].body if ep.requests else None
                    },
                    "sample_response": {
                        "status": ep.responses[0].status if ep.responses else 200,
                        "body": ep.responses[0].body if ep.responses else None
                    }
                }
                for ep in self.api_endpoints
            ]
        }
