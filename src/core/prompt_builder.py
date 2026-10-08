"""
MockClaw Prompt Builder
Constructs LLM prompts from endpoint data for mock generation.
"""

from __future__ import annotations

import json
from typing import Any


SYSTEM_PROMPT = """You are an expert API architect. Given HTTP request/response pairs, generate a Python FastAPI mock endpoint.

Requirements:
1. Use Pydantic models for request/response validation
2. Use realistic hardcoded sample data matching the original response structure
3. If the response contains a list, generate exactly 3 representative items
4. Handle path parameters (e.g., /users/{user_id}) correctly via FastAPI path syntax
5. Accept query parameters as typed function arguments with defaults
6. Mirror observed error status codes faithfully — return 4xx/5xx responses that match the provided samples
7. Only use standard library and fastapi/pydantic — no third-party packages like faker
8. When multiple responses are present, generate conditional branches matching the observed data

Generate ONLY the Python code with:
- Pydantic models for structured request/response schemas
- FastAPI route decorators (@app.get, @app.post, etc.)
- Hardcoded realistic sample data
- Type hints throughout

Return ONLY the Python code in a markdown code block labeled 'python'."""


# A recorded body can be enormous: a list endpoint with a few thousand rows
# produced a 260KB capture, and pasting it whole made a 66k-token prompt, so
# the call fails on the model's context limit or costs far more than one
# endpoint is worth. What the model copies from the body is its structure, and
# the start of it carries that.
_MAX_BODY_CHARS = 4000


def _body_for_prompt(body: Any) -> str:
    """Render a recorded body for the prompt, capped, with the cut marked."""
    if not body:
        # Absent and null both mean "no body here" (the parser stores None for
        # a body that was not recorded), and get('body', 'N/A') prints the
        # literal None because the key exists.
        return "N/A"
    text = body if isinstance(body, str) else str(body)
    if len(text) <= _MAX_BODY_CHARS:
        return text
    return f"{text[:_MAX_BODY_CHARS]}... (truncated, {len(text)} characters recorded)"


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
            f"- Body: {_body_for_prompt(req.get('body'))}\n"
            f"- Query Params: {json.dumps(req.get('query_params', {}), indent=2)}\n\n"
            f"Sample Response:\n"
            f"- Status: {resp.get('status', 200)}\n"
            f"- Body: {_body_for_prompt(resp.get('body'))}"
        )

        if len(all_responses) > 1:
            prompt += "\n\nAdditional observed responses:"
            for i, r in enumerate(all_responses[1:], start=2):
                prompt += f"\n  [{i}] status {r.get('status', 200)}: {(r.get('body') or '')[:120]}"

        return prompt
