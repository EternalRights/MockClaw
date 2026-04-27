"""
MockClaw Code Extractor
Extracts Python code blocks from LLM responses.
"""

from __future__ import annotations

import re


class CodeExtractor:
    """Extracts Python code from LLM response text.

    Handles both explicit `````python`` fenced blocks and generic
    fenced code blocks.  Falls back to returning the raw response
    when no code block is detected.
    """

    _PYTHON_BLOCK = re.compile(r"```python\n(.*?)```", re.DOTALL)
    _GENERIC_BLOCK = re.compile(r"```\n?(.*?)```", re.DOTALL)

    def extract_code(self, response: str) -> str:
        """Extract Python code from an LLM response.

        Args:
            response: Raw LLM response text.

        Returns:
            Extracted Python code, or the stripped original response
            if no code block is found.
        """
        if match := self._PYTHON_BLOCK.search(response):
            return match.group(1).strip()
        if match := self._GENERIC_BLOCK.search(response):
            return match.group(1).strip()
        return response.strip()
