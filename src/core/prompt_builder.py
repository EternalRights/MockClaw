"""
MockClaw Prompt Builder
Constructs LLM prompts from endpoint data for mock generation.
"""

from __future__ import annotations

import json
from typing import Any


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


class PromptBuilder:
    """Builds LLM prompts from HAR endpoint data.

    Transforms structured endpoint information into a natural-language
    prompt that instructs the LLM to generate a FastAPI mock endpoint.
    """

    def build_prompt(self, endpoint_data: dict[str, Any]) -> str:
        """Build the LLM prompt for endpoint generation.

        Args:
            endpoint_data: Dictionary containing endpoint information
                including method, path, sample request, and sample response(s).

        Returns:
            Formatted prompt string for the LLM.
        """
        req = endpoint_data.get("sample_request", {})
        all_responses = endpoint_data.get("sample_responses", [])
        resp = all_responses[0] if all_responses else {}

        prompt = (
            f"Generate a FastAPI mock endpoint for:\n\n"
            f"Method: {endpoint_data['method']}\n"
            f"Path: {endpoint_data['resource_path']}\n\n"
            f"Sample Request:\n"
            f"- Body: {req.get('body', 'N/A')}\n"
            f"- Query Params: {json.dumps(req.get('query_params', {}), indent=2)}\n\n"
            f"Sample Response:\n"
            f"- Status: {resp.get('status', 200)}\n"
            f"- Body: {resp.get('body', 'N/A')}"
        )

        if len(all_responses) > 1:
            prompt += "\n\nAdditional observed responses:"
            for i, r in enumerate(all_responses[1:], start=2):
                prompt += f"\n  [{i}] status {r.get('status', 200)}: {(r.get('body') or '')[:120]}"

        return prompt
