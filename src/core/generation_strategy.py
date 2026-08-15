"""
MockClaw Generation Strategies
Strategy pattern for mock endpoint code generation.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from .code_extractor import CodeExtractor
from .llm_client_manager import LLMClientManager
from .prompt_builder import PromptBuilder, SYSTEM_PROMPT
from .route_builder import build_route, generate_func_name


class GenerationStrategy(ABC):
    """Abstract base class for mock endpoint generation strategies."""

    def __init__(self, simulate_latency: bool = False) -> None:
        self._simulate_latency = simulate_latency

    @abstractmethod
    def generate(self, endpoint_data: dict[str, Any]) -> str:
        """Generate FastAPI route code for a single endpoint."""
        ...

    async def generate_async(self, endpoint_data: dict[str, Any]) -> str:
        """Async variant of generate -- defaults to sync in executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.generate, endpoint_data)

    def _resolve_latency(self, endpoint_data: dict[str, Any]) -> int:
        """Return the latency (ms) to simulate for this endpoint.

        Returns ``0`` when latency simulation is disabled or the HAR data
        carried no timing information.
        """
        if not self._simulate_latency:
            return 0
        return int(endpoint_data.get("avg_latency_ms", 0) or 0)

    @staticmethod
    def _extract_common(
        endpoint_data: dict[str, Any],
    ) -> tuple[str, str, list[dict[str, Any]], dict[str, Any]]:
        """Extract method, path, normalised responses, and sample request.

        Handles the common pre-processing shared by template and smart-routing
        strategies: pulling out method/path, collecting all responses, and
        back-filling request bodies from ``sample_request`` when individual
        responses don't carry their own.

        Returns:
            ``(method, path, all_responses, sample_request)`` ready for
            :func:`build_route`.
        """
        method = endpoint_data["method"]
        path = endpoint_data["resource_path"]
        sample_request = endpoint_data.get("sample_request", {})
        all_responses: list[dict[str, Any]] = endpoint_data.get(
            "sample_responses",
            [],
        )

        if not all_responses:
            all_responses = [{}]

        has_individual_requests = any(
            resp.get("request") and resp["request"].get("body")
            for resp in all_responses
        )

        if not has_individual_requests:
            request_body = sample_request.get("body")
            if request_body:
                all_responses = [
                    {**resp, "request": {"body": request_body}}
                    for resp in all_responses
                ]

        return method, path, all_responses, sample_request


class LLMGenerationStrategy(GenerationStrategy):
    """Generate endpoints using an LLM (OpenAI-compatible API).

    When the LLM client is unavailable or the call fails, the strategy
    automatically falls back to the configured fallback strategy.
    """

    def __init__(
        self,
        client_manager: LLMClientManager,
        prompt_builder: PromptBuilder,
        code_extractor: CodeExtractor,
        model: str = "gpt-4o-mini",
        fallback: GenerationStrategy | None = None,
    ) -> None:
        self._client_manager = client_manager
        self._prompt_builder = prompt_builder
        self._code_extractor = code_extractor
        self._model = model
        self._fallback = fallback

    def generate(self, endpoint_data: dict[str, Any]) -> str:
        client = self._client_manager.get_client()
        if not client:
            if self._fallback:
                return self._fallback.generate(endpoint_data)
            raise RuntimeError("LLM client not available and no fallback configured")

        try:
            response = self._client_manager.call_with_retry(
                client.chat.completions.create,
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": self._prompt_builder.build_prompt(endpoint_data)},
                ],
                temperature=0.3,
                max_tokens=2000,
            )
            return self._code_extractor.extract_code(
                response.choices[0].message.content or ""
            )
        except Exception:
            if self._fallback:
                return self._fallback.generate(endpoint_data)
            raise RuntimeError("LLM generation failed and no fallback configured")

    async def generate_async(self, endpoint_data: dict[str, Any]) -> str:
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.generate, endpoint_data)


class TemplateGenerationStrategy(GenerationStrategy):
    """Generate endpoints using template-based fallback.

    Creates a simple FastAPI route that returns the HAR response data
    directly.
    """

    def generate(self, endpoint_data: dict[str, Any]) -> str:
        method, path, all_responses, sample_request = self._extract_common(endpoint_data)
        func_name = generate_func_name(method, path)
        return build_route(
            method,
            path,
            all_responses,
            func_name,
            use_smart_fallback=False,
            sample_request=sample_request,
            latency_ms=self._resolve_latency(endpoint_data),
        )


class SmartRoutingStrategy(GenerationStrategy):
    """Generate endpoints with smart conditional routing.

    Analyzes request bodies to find fields with differing values and
    generates if/elif/else routing logic so that different request
    payloads receive the appropriate response.
    """

    def generate(self, endpoint_data: dict[str, Any]) -> str:
        method, path, all_responses, sample_request = self._extract_common(endpoint_data)
        func_name = generate_func_name(method, path)
        return build_route(
            method,
            path,
            all_responses,
            func_name,
            use_smart_fallback=True,
            sample_request=sample_request,
            latency_ms=self._resolve_latency(endpoint_data),
        )
