"""
MockClaw Code Extractor Tests

The extractor sits between a model's free-form reply and the generated
server, so a leftover language tag here becomes a runtime error there.
"""

import pytest
from fastapi import FastAPI

from core.code_extractor import CodeExtractor

CODE = '@app.get("/api/x")\nasync def get_api_x():\n    return {"ok": True}'


@pytest.fixture
def extractor():
    return CodeExtractor()


def fence(tag, same_line=False):
    if not tag:
        return f"```\n{CODE}\n```"
    joiner = " " if same_line else "\n"
    return f"```{tag}{joiner}{CODE}\n```"


class TestLanguageTags:
    """Every spelling of the python tag must strip cleanly."""

    @pytest.mark.parametrize("tag", ["python", "Python", "PYTHON", "py", "Py", "python3"])
    def test_tag_is_stripped(self, extractor, tag):
        assert extractor.extract_code(fence(tag)) == CODE

    def test_untagged_block(self, extractor):
        assert extractor.extract_code(fence("")) == CODE

    def test_code_on_the_tag_line(self, extractor):
        assert extractor.extract_code(fence("python", same_line=True)) == CODE

    def test_surrounding_prose_is_ignored(self, extractor):
        text = f"Sure, here it is:\n\n{fence('Python')}\n\nHope that helps."
        assert extractor.extract_code(text) == CODE

    def test_no_fence_returns_the_response(self, extractor):
        assert extractor.extract_code(f"  {CODE}  ") == CODE


class TestExtractedCodeRuns:
    """A stripped tag must not survive into the generated server."""

    @pytest.mark.parametrize("tag", ["python", "Python", "py", "python3"])
    def test_block_imports_without_a_stray_name(self, extractor, tag):
        # A bare `Python` line is a valid expression statement, so compile()
        # accepted it and the corruption only surfaced as a NameError when
        # the generated module was imported.
        code = extractor.extract_code(fence(tag))
        namespace = {"app": FastAPI()}
        exec(compile(code, "<generated>", "exec"), namespace)
        assert "get_api_x" in namespace

    def test_prefers_the_python_block(self, extractor):
        text = (
            "```bash\npip install pytest\n```\n\n"
            f"{fence('python')}\n"
        )
        assert extractor.extract_code(text) == CODE
