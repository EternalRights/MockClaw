"""
MockClaw Code Extractor
Extracts Python code blocks from LLM responses.
"""

from __future__ import annotations

import re


# A fence line is ```<info string>: the language tag, usually, but models also
# write ```python title=api.py. CommonMark puts the code on the next line, so
# the info string is not code. Treating it as code left a bare `javascript` (or
# `title=api.py`) at the head of the snippet -- both of which *compile* as
# expression statements, so they survived validation and then raised NameError
# when the generated mock server was imported, taking every endpoint down.
#
# A model that puts its first statement on the fence line is still tolerated,
# so a remainder is only dropped when it reads as an info string: no code
# punctuation, and no statement keyword at its head. The allowed characters
# cover what tags and attributes actually look like -- `python3`,
# `text/plain`, `application/xml`, `title=api.py`.
_INFO_STRING = re.compile(r"^[A-Za-z0-9_.:\-=/+ \t]+$")
_CODE_PUNCTUATION = re.compile(r"[@()\[\]{}\"'#\\;]")
_STATEMENT_START = re.compile(
    r"^(?:import|from|def|class|return|if|for|while|with|try|async|await|@)\b"
)

# What registering a route looks like. The generator emits exactly one route
# per endpoint, so a snippet that only imports or defines helpers is not a
# usable answer -- it compiles, registers nothing, and the endpoint would
# silently answer 404 while the template that would have worked is discarded.
_ROUTE_MARKERS = (
    re.compile(
        r"@\s*[\w.]+\s*\.\s*(?:get|post|put|patch|delete|head|options|trace|api_route)\s*\(",
        re.IGNORECASE,
    ),
    re.compile(r"\badd_api_route\s*\("),
)


def _is_info_string(text: str) -> bool:
    """Whether a fence-line remainder is an info string rather than code."""
    text = text.strip()
    if not text:
        return True
    if _CODE_PUNCTUATION.search(text):
        return False
    if not _INFO_STRING.match(text):
        return False
    return not _STATEMENT_START.match(text)


def defines_route(code: str) -> bool:
    """Whether *code* registers a FastAPI route."""
    return any(marker.search(code) for marker in _ROUTE_MARKERS)


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
    - `` ```javascript `` / `` ```python title=api.py ``: the info string
      belongs to the fence, not to the code
    """

    # `python\d*|py\d*` rather than `py|python`: alternation is ordered, so
    # listing the shorter branch first would match "py" inside "python3" and
    # leave "thon3" at the head of the extracted code.
    #
    # The info string is captured separately so `_fence_body` can decide
    # whether it is a tag or a statement that happens to sit on the fence line.
    _PYTHON_BLOCK = re.compile(
        r"```[ \t]*(?:python\d*|py\d*)(?P<info>[^\n]*)\n?(?P<body>.*?)```",
        re.DOTALL | re.IGNORECASE,
    )
    _GENERIC_BLOCK = re.compile(
        r"```(?P<info>[^\n]*)\n?(?P<body>.*?)```", re.DOTALL
    )

    def extract_code(self, response: str) -> str:
        """Extract Python code from an LLM response.

        Args:
            response: Raw LLM response text.

        Returns:
            Extracted Python code, or the stripped original response
            if no code block is found.
        """
        blocks = [self._fence_body(m) for m in self._PYTHON_BLOCK.finditer(response)]
        blocks = [block for block in blocks if block]
        if blocks:
            # A reply can fence an import-only explanation before the route
            # itself; taking the first block verbatim dropped the route.
            return next((b for b in blocks if defines_route(b)), blocks[0])

        if match := self._GENERIC_BLOCK.search(response):
            return self._fence_body(match)
        return response.strip()

    @staticmethod
    def _fence_body(match: re.Match[str]) -> str:
        """Code inside a fence, with the fence's info string dropped."""
        info = match.group("info")
        body = match.group("body")
        if not body.strip():
            # A single-line fence carries its content on the fence line.
            return info.strip()
        if info.strip() and _is_info_string(info):
            return body.strip()
        return f"{info}\n{body}".strip()
