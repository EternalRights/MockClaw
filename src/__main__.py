"""
MockClaw entry point for `python -m mockclaw`.

When invoked via ``python -m mockclaw``, this runs the CLI application
directly, providing the same interface as the ``mockclaw`` console script.
"""

from .cli import app

app()