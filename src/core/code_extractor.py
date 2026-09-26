"""
MockClaw Code Extractor
Extracts Python code blocks from LLM responses.
"""

from __future__ import annotations

import re


class CodeExtractor:
    """Extracts Python code from LLM response text.

    Handles both explicit ``python`` fenced blocks and generic
    fenced code blocks.  Falls back to returning the raw response
    when no code block is detected.

    Robust against common LLM formatting variations:
    - `` ```python\\n `` (newline after language tag)
    - `` ```python `` (space then code on same line)
    - `` ``` `` without language specifier
    - `` ```Python `` / `` ```py `` / `` ```python3 ``: models do not agree
      on the spelling of the language tag, and matching only the lower-case
      ``python`` let the tag leak into the extracted code
    """

    # `python\d*|py\d*` rather than `py|python`: alternation is ordered, so
    # listing the shorter branch first would match "py" inside "python3" and
    # leave "thon3" at the head of the extracted code.
    _PYTHON_BLOCK = re.compile(
        r"```(?:python\d*|py\d*)[ \t]*\n?(.*?)```", re.DOTALL | re.IGNORECASE
    )
    _GENERIC_BLOCK = re.compile(r"```\s*\n?(.*?)```", re.DOTALL)

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
