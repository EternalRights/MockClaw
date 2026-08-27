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


class TestStatsCommand:
    """Tests for the 'stats' command."""

    def test_stats_missing_directory(self):
        result = runner.invoke(app, ["stats", "./nonexistent_dir_xyz"])
        assert result.exit_code != 0

    def test_stats_text_output(self, tmp_path):
        mock_file = tmp_path / "dynamic_api.py"
        mock_file.write_text(
            '@app.get("/api/users")\n'
            'async def get_api_users():\n'
            '    return {"users": []}\n\n'
            '@app.post("/api/login")\n'
            'async def post_api_login():\n'
            '    return {"token": "abc"}\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["stats", str(tmp_path)])
        assert result.exit_code == 0
        assert "Total Endpoints" in result.stdout
        assert "GET" in result.stdout
        assert "POST" in result.stdout

    def test_stats_json_output(self, tmp_path):
        mock_file = tmp_path / "dynamic_api.py"
        mock_file.write_text(
            '@app.get("/api/health")\n'
            'async def get_api_health():\n'
            '    return {"status": "ok"}\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["stats", str(tmp_path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["total_endpoints"] == 1
        assert "endpoints" in data

    def test_stats_filters_builtin_endpoints(self, tmp_path):
        mock_file = tmp_path / "dynamic_api.py"
        mock_file.write_text(
            '@app.get("/health")\n'
            'async def health():\n'
            '    return {"status": "OK"}\n\n'
            '@app.get("/api/data")\n'
            'async def get_api_data():\n'
            '    return {"data": [1, 2, 3]}\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["stats", str(tmp_path), "--json"])
        data = json.loads(result.stdout)
        assert data["total_endpoints"] == 1

    def test_stats_detects_smart_routing(self, tmp_path):
        mock_file = tmp_path / "dynamic_api.py"
        mock_file.write_text(
            '@app.post("/api/checkout")\n'
            'async def post_api_checkout(request: Request):\n'
            '    body = await request.json()\n'
            '    return {"status": "ok"}\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["stats", str(tmp_path), "--json"])
        data = json.loads(result.stdout)
        assert data["smart_routing_count"] == 1

    def test_stats_detects_latency(self, tmp_path):
        mock_file = tmp_path / "dynamic_api.py"
        mock_file.write_text(
            '@app.get("/api/slow")\n'
            'async def get_api_slow():\n'
            '    await asyncio.sleep(0.200)\n'
            '    return {"ok": true}\n\n'
            '@app.get("/api/fast")\n'
            'async def get_api_fast():\n'
            '    return {"ok": true}\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["stats", str(tmp_path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["latency"]["simulated_endpoints"] == 1
        assert data["latency"]["avg_latency_ms"] == 200.0

    def test_stats_detects_latency_after_long_docstring(self, tmp_path):
        # A long multi-scenario docstring pushes the sleep line past any
        # fixed 500-char window; the scan must still find it.
        scenarios = "".join(
            f'    [ {i}] status 200: {"x" * 60}\n' for i in range(1, 30)
        )
        mock_file = tmp_path / "dynamic_api.py"
        mock_file.write_text(
            '@app.get("/api/big")\n'
            'async def get_api_big():\n'
            f'    """Mock endpoint -- 29 HAR scenarios recorded.\n{scenarios}    """\n'
            '    await asyncio.sleep(0.350)\n'
            '    return {"ok": true}\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["stats", str(tmp_path), "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["latency"]["simulated_endpoints"] == 1
        assert data["latency"]["avg_latency_ms"] == 350.0
