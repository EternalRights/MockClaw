"""
MockClaw CLI Test Suite
"""

import json
import os
import pytest
from pathlib import Path
from typer.testing import CliRunner
import sys

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from cli import app

runner = CliRunner()


class TestCLIHelp:
    def test_main_help(self):
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "mockclaw" in result.stdout.lower() or "generate" in result.stdout.lower()

    def test_generate_help(self):
        result = runner.invoke(app, ["generate", "--help"])
        assert result.exit_code == 0
        assert "har" in result.stdout.lower() or "input" in result.stdout.lower()

    def test_serve_help(self):
        result = runner.invoke(app, ["serve", "--help"])
        assert result.exit_code == 0
        assert "mock" in result.stdout.lower() or "directory" in result.stdout.lower()


class TestGenerateCommand:
    def test_generate_missing_har(self):
        result = runner.invoke(app, ["generate", "nonexistent.har", "./out"])
        assert result.exit_code != 0, "Should fail for missing HAR file"

    def test_generate_produces_output(self, tmp_path, minimal_har_data):
        har_file = tmp_path / "test.har"
        har_file.write_text(json.dumps(minimal_har_data), encoding="utf-8")

        output_dir = str(tmp_path / "mocks")
        result = runner.invoke(app, [
            "generate",
            str(har_file),
            output_dir,
            "--smart-fallback",
        ])
        assert result.exit_code == 0, f"Generate failed: {result.output}"
        assert os.path.exists(os.path.join(output_dir, "dynamic_api.py")), \
            "Generated file should exist"


class TestServeCommand:
    def test_serve_missing_directory(self):
        result = runner.invoke(app, ["serve", "./nonexistent_dir_xyz"])
        assert result.exit_code != 0, "Should fail for missing directory"


class TestCLIErrorHandling:
    def test_invalid_command(self):
        result = runner.invoke(app, ["invalid-command"])
        assert result.exit_code != 0 or "help" in result.stdout.lower()

    def test_no_arguments(self):
        result = runner.invoke(app, [])
        assert result.exit_code in [0, 2]
