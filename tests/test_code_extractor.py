"""
MockClaw Code Extractor Tests

The extractor sits between a model's free-form reply and the generated
server, so a leftover language tag here becomes a runtime error there.
"""

import pytest
from fastapi import FastAPI

from core.code_extractor import CodeExtractor, defines_route

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


class TestFenceInfoString:
    """The fence line is an info string, not code.

    A leaked tag became a bare expression statement (`javascript`, or
    `title=api.py`) at the head of the snippet. Both compile, so validation
    let them through, and the generated mock server then died with NameError
    on import -- taking every endpoint down with it.
    """

    @pytest.mark.parametrize("tag", [
        "javascript", "text", "text/plain", "application/xml", "bash",
    ])
    def test_non_python_tag_is_stripped(self, extractor, tag):
        assert extractor.extract_code(fence(tag)) == CODE

    @pytest.mark.parametrize("tag", [
        "python title=api.py", "python linenos", "python3 name=handler",
    ])
    def test_python_tag_attributes_are_stripped(self, extractor, tag):
        assert extractor.extract_code(fence(tag)) == CODE

    def test_statement_on_the_fence_line_is_kept(self, extractor):
        # `from fastapi import FastAPI` reads as an info string by character
        # class, so the keyword check is what keeps it from being dropped.
        text = f"```python from fastapi import FastAPI\n{CODE}\n```"
        extracted = extractor.extract_code(text)
        assert extracted.startswith("from fastapi import FastAPI")
        assert CODE in extracted

    def test_route_block_is_preferred_over_an_import_block(self, extractor):
        # First block compiles but registers nothing; using it dropped the
        # endpoint while discarding the route the model did provide.
        text = (
            "```python\nfrom fastapi import APIRouter\n```\n\n"
            f"{fence('python')}\n"
        )
        assert extractor.extract_code(text) == CODE


class TestIndentedFence:
    """A model may indent its whole fence; the snippet is still the code.

    Models do this when the reply is written as a list item or under a
    sub-heading. The indent made the block fail to compile, so the answer was
    rejected as unusable and the endpoint fell back to the plain template --
    the model's work discarded for a formatting accident.
    """

    @staticmethod
    def _indented(tag="python", indent="  "):
        body = "\n".join(indent + line for line in CODE.splitlines())
        opening = f"{indent}```{tag}" if tag else f"{indent}```"
        return f"Here it is:\n{opening}\n{body}\n{indent}```\n"

    @pytest.mark.parametrize("tag", ["python", "", "py", "python3"])
    def test_the_common_indent_is_removed(self, extractor, tag):
        assert extractor.extract_code(self._indented(tag)) == CODE

    def test_the_extracted_code_compiles_and_registers_a_route(self, extractor):
        code = extractor.extract_code(self._indented())

        compile(code, "<extracted>", "exec")
        assert defines_route(code)

    def test_a_four_space_indent_is_removed_too(self, extractor):
        assert extractor.extract_code(self._indented(indent="    ")) == CODE

    def test_no_common_indent_is_left_alone(self, extractor):
        # Only the indentation every line shares is removed, so a block laid
        # out differently is untouched.
        ragged = '@app.get("/api/x")\n    async def get_api_x():\n        return {"ok": True}'
        assert extractor.extract_code(f"```python\n{ragged}\n```") == ragged


class TestDefinesRoute:
    def test_route_decorators(self):
        for decorator in [
            '@app.get("/x")', '@app.post("/x")', '@router.put("/x")',
            '@app.api_route("/x", methods=["GET"])',
        ]:
            assert defines_route(f"{decorator}\nasync def x():\n    return {{}}\n")

    def test_add_api_route(self):
        assert defines_route('app.add_api_route("/x", x, methods=["GET"])\n')

    def test_helper_only_code_is_not_a_route(self):
        assert not defines_route("from fastapi import APIRouter\n")
        assert not defines_route("def helper():\n    return 1\n")
        assert not defines_route("")


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

    @pytest.mark.parametrize("tag", ["javascript", "python title=api.py"])
    def test_tolerated_fence_still_imports(self, extractor, tag):
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
