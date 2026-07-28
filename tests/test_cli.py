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


class TestInfoCommand:
    """Tests for the 'info' command."""

    def test_info_text_output(self):
        result = runner.invoke(app, ["info"])
        assert result.exit_code == 0
        stdout = result.stdout
        assert "MockClaw" in stdout
        assert "Python" in stdout
        assert "Platform" in stdout

    def test_info_json_output(self):
        result = runner.invoke(app, ["info", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "mockclaw" in data
        assert "python" in data
        assert "dependencies" in data
        assert "environment" in data
        assert isinstance(data["dependencies"], dict)

    def test_info_json_short_flag(self):
        result = runner.invoke(app, ["info", "-j"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "mockclaw" in data


class TestVersionFlag:
    """Tests for the --version / -v flag."""

    def test_version_long_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "MockClaw" in result.stdout
        assert "version" in result.stdout.lower()

    def test_version_short_flag(self):
        result = runner.invoke(app, ["-v"])
        assert result.exit_code == 0
        assert "MockClaw" in result.stdout
