"""
MockClaw AI Generator
Uses LLM to generate FastAPI mock endpoints from parsed HAR data.
"""

import os
import re
import json
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

# Optional OpenAI integration
try:
    from openai import OpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


SYSTEM_PROMPT = """You are an expert API architect. Given this HTTP request/response pair, generate a Python FastAPI endpoint.

Requirements:
1. Use Pydantic models for request/response validation
2. Use 'Faker' library to generate realistic fake data for fields like 'name', 'email', 'address', 'phone', 'id'
3. If the response contains a list, generate exactly 5 items
4. Handle path parameters (e.g., /users/{user_id}) correctly
5. Support query parameters for filtering
6. If request has a query param `?status=error`, return a 500 error with a specific error message
7. Include proper HTTP status codes and error handling

Generate ONLY the Python code with:
- Pydantic models for request/response
- FastAPI route decorators (@app.get, @app.post, etc.)
- Faker data generation
- Type hints throughout

Return ONLY the Python code in a markdown code block labeled 'python'."""

@dataclass
class GenerationResult:
    """Result of mock generation."""
    success: bool
    generated_code: str
    endpoint_path: str
    error: Optional[str] = None


class MockGenerator:
    """Generates FastAPI mock endpoints using LLM."""
    
    def __init__(self, api_key: Optional[str] = None, model: Optional[str] = None):
        self.api_key = api_key or os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.provider = os.getenv("LLM_PROVIDER", "openai")
        self.base_url = os.getenv("LLM_BASE_URL")
        self.model = model or os.getenv("MODEL_NAME", "gpt-4o-mini")
        self.client = None
        
        if OPENAI_AVAILABLE and self.api_key:
            client_kwargs = {"api_key": self.api_key}
            if self.base_url:
                client_kwargs["base_url"] = self.base_url
            self.client = OpenAI(**client_kwargs)
    
    def _build_prompt(self, endpoint_data: dict) -> str:
        """Build the LLM prompt from endpoint data."""
        return f"""Generate a FastAPI mock endpoint for:

Method: {endpoint_data['method']}
Path: {endpoint_data['resource_path']}

Sample Request:
- URL: {endpoint_data.get('sample_request', {}).get('url', 'N/A')}
- Headers: {json.dumps(endpoint_data.get('sample_request', {}).get('headers', {}), indent=2)}
- Body: {endpoint_data.get('sample_request', {}).get('body', 'N/A')}
- Query Params: {json.dumps(endpoint_data.get('sample_request', {}).get('query_params', {}), indent=2)}

Sample Response:
- Status: {endpoint_data.get('sample_response', {}).get('status', 200)}
- Content-Type: {endpoint_data.get('sample_response', {}).get('content_type', 'application/json')}
- Body: {endpoint_data.get('sample_response', {}).get('body', 'N/A')}

Generate a complete FastAPI mock endpoint."""

    def _extract_code_from_response(self, response: str) -> str:
        """Extract Python code from LLM response."""
        # Try to find code block
        code_match = re.search(r'```python\n(.*?)```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        # Fallback: try generic code block
        code_match = re.search(r'```\n?(.*?)```', response, re.DOTALL)
        if code_match:
            return code_match.group(1).strip()
        
        return response.strip()
    
    def _generate_with_llm(self, endpoint_data: dict) -> str:
        """Call LLM to generate mock code."""
        if not self.client:
            return self._generate_fallback_code(endpoint_data)
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._build_prompt(endpoint_data)}
                ],
                temperature=0.3,
                max_tokens=2000
            )
            return self._extract_code_from_response(response.choices[0].message.content)
        except Exception as e:
            print(f"LLM generation failed: {e}")
            return self._generate_fallback_code(endpoint_data)
    
    def _generate_fallback_code(self, endpoint_data: dict) -> str:
        """Generate fallback mock code without LLM."""
        method = endpoint_data['method']
        path = endpoint_data['resource_path']
        response_body = endpoint_data.get('sample_response', {}).get('body', '{}')
        response_status = endpoint_data.get('sample_response', {}).get('status', 200)
        
        # Try to extract JSON structure
        try:
            if response_body and response_body != 'N/A':
                parsed = json.loads(response_body)
                body_sample = json.dumps(parsed, indent=4)
            else:
                body_sample = '{"message": "mock response"}'
        except:
            body_sample = '{"message": "mock response"}'
        
        return '''"""
Mock endpoint for ''' + method + ''' ''' + path + '''
Auto-generated by MockClaw
"""
from fastapi import APIRouter, Query, Path, HTTPException, status
from pydantic import BaseModel, Field
from typing import Optional, List, Any
from faker import Faker
import random

fake = Faker()
router = APIRouter()

# Response Models
class MockResponse(BaseModel):
    data: Any = Field(default_factory=lambda: {
        "id": random.randint(1, 1000),
        "message": "mock response",
        "generated": True
    })


# Mock endpoint for ''' + method + ''' ''' + path + '''
@app.''' + method.lower() + '''("''' + path + '''")
async def mock_''' + method.lower() + '''_endpoint():
    """
    Mock endpoint auto-generated by MockClaw
    """
    # Check for error simulation
    if status_param := "error":
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "Simulated error response", "status": "error"}
        )
    
    # Generate mock response data
    mock_data = ''' + body_sample + '''
    
    return MockResponse(data=mock_data)
'''

    def generate_endpoint(self, endpoint_data: dict) -> GenerationResult:
        """Generate mock code for a single endpoint."""
        try:
            generated_code = self._generate_with_llm(endpoint_data)
            
            # Post-process: add import statements
            if 'from fastapi import' not in generated_code.lower():
                generated_code = self._add_imports(generated_code)
            
            return GenerationResult(
                success=True,
                generated_code=generated_code,
                endpoint_path=endpoint_data['resource_path']
            )
        except Exception as e:
            return GenerationResult(
                success=False,
                generated_code="",
                endpoint_path=endpoint_data['resource_path'],
                error=str(e)
            )
    
    def _add_imports(self, code: str) -> str:
        """Add necessary imports to generated code."""
        imports = [
            "from fastapi import APIRouter, Query, Path, HTTPException, status",
            "from pydantic import BaseModel, Field",
            "from typing import Optional, List, Any, Dict",
            "from faker import Faker",
            "import random",
            "",
            "fake = Faker()",
            "router = APIRouter()",
            ""
        ]
        
        # Check what imports are needed
        needs_faker = 'faker' in code.lower() or 'fake.' in code.lower()
        needs_pydantic = 'pydantic' in code.lower() or 'basemodel' in code.lower()
        needs_random = 'random.' in code.lower()
        
        final_imports = ["from fastapi import FastAPI, APIRouter, Query, Path, HTTPException, status",
                        "from pydantic import BaseModel, Field",
                        "from typing import Optional, List, Any, Dict",
                        "import random"]
        
        if 'Faker' in code:
            final_imports.append("from faker import Faker\nfake = Faker()")
        
        # Build final code
        if '# Generated by' in code or '"""Mock' in code:
            return code
        
        return "\n".join(final_imports) + "\n\n" + code

    def generate_all(self, endpoints: list[dict], output_dir: str = "generated_mocks") -> list[GenerationResult]:
        """Generate mock code for all endpoints."""
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        results = []
        all_code = ["# MockClaw Auto-Generated Mocks\n", 
                    "from fastapi import FastAPI, APIRouter, Query, Path, HTTPException, status",
                    "from pydantic import BaseModel, Field",
                    "from typing import Optional, List, Any, Dict",
                    "import random",
                    "from faker import Faker",
                    "import json",
                    "",
            "fake = Faker()",
            "app = FastAPI(title='MockClaw Generated API')",
            "router = APIRouter()",
            "",
            "# === Health Endpoints ===",
            '@app.get("/health")',
            'async def health_check():',
            '    """Health check endpoint."""',
            '    return {"status": "OK", "service": "MockClaw"}',
            "",
            '@app.get("/mockclaw/info")',
            'async def mockclaw_info():',
            '    """MockClaw metadata endpoint."""',
            '    return {',
            '        "generator": "MockClaw",',
            '        "version": "0.1.0",',
            '        "endpoints": []',
            '    }',
            "",
            "# === Generated Endpoints ===",
            ""
        ]
        
        for endpoint in endpoints:
            result = self.generate_endpoint(endpoint)
            results.append(result)
            
            if result.success:
                # Add to combined file
                all_code.append(f"# Endpoint: {result.endpoint_path}")
                all_code.append(result.generated_code)
                all_code.append("")
        
        # Write combined file
        combined_path = output_path / "dynamic_api.py"
        combined_path.write_text("\n".join(all_code), encoding='utf-8')
        
        return results


def main():
    """CLI for testing generation."""
    import sys
    from parser import HARParser
    
    if len(sys.argv) < 2:
        print("Usage: python generator.py <path_to_har_file>")
        sys.exit(1)
    
    # Parse HAR file
    parser = HARParser(sys.argv[1])
    endpoints_data = parser.export_as_dict()
    
    # Generate mocks
    generator = MockGenerator()
    results = generator.generate_all(endpoints_data['endpoints'])
    
    print(f"Generated {len(results)} endpoints:")
    for r in results:
        status = "✓" if r.success else "✗"
        print(f"  {status} {r.endpoint_path}")


if __name__ == "__main__":
    main()
