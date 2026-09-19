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

    # --- status codes -------------------------------------------------

    def test_stats_reports_json_response_status(self, tmp_path):
        # Non-200 successes are emitted as JSONResponse(status_code=...), and
        # scanning only for raises reported them as a default 200.
        (tmp_path / "dynamic_api.py").write_text(
            '@app.post("/api/made")\n'
            'async def post_api_made():\n'
            '    return JSONResponse(status_code=201, content={"id": 7})\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["stats", str(tmp_path), "--json"])
        data = json.loads(result.stdout)
        assert data["endpoints"]["POST /api/made"]["status_codes"] == ["201"]

    def test_stats_reports_raise_status(self, tmp_path):
        (tmp_path / "dynamic_api.py").write_text(
            '@app.get("/api/gone")\n'
            'async def get_api_gone():\n'
            '    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"e": 1})\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["stats", str(tmp_path), "--json"])
        data = json.loads(result.stdout)
        assert data["endpoints"]["GET /api/gone"]["status_codes"] == ["404"]

    def test_stats_defaults_to_200_for_a_plain_return(self, tmp_path):
        (tmp_path / "dynamic_api.py").write_text(
            '@app.get("/api/ok")\n'
            'async def get_api_ok():\n'
            '    return {"ok": True}\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["stats", str(tmp_path), "--json"])
        data = json.loads(result.stdout)
        assert data["endpoints"]["GET /api/ok"]["status_codes"] == ["200"]

    # --- endpoint discovery -------------------------------------------

    def test_stats_discovers_api_route_endpoints(self, tmp_path):
        # Verbs FastAPI has no shorthand for are emitted as api_route and
        # used to be skipped entirely, undercounting total_endpoints.
        (tmp_path / "dynamic_api.py").write_text(
            '@app.api_route("/api/dav", methods=["PROPFIND"])\n'
            'async def propfind_api_dav():\n'
            '    return {"dav": True}\n',
            encoding="utf-8",
        )
        result = runner.invoke(app, ["stats", str(tmp_path), "--json"])
        data = json.loads(result.stdout)
        assert data["total_endpoints"] == 1
        assert data["method_counts"] == {"PROPFIND": 1}

    def test_stats_matches_generated_output(self, tmp_path):
        # End-to-end: generate from a HAR, then read the report back.
        from core.generator import MockGenerator
        from core.parser import HARParser

        def entry(method, url, status, body='{"ok": true}'):
            return {
                "request": {"method": method, "url": url,
                            "headers": [], "queryString": []},
                "response": {"status": status, "headers": [],
                             "content": {"mimeType": "application/json",
                                         "text": body}},
                "time": 10,
            }

        har_path = tmp_path / "t.har"
        har_path.write_text(json.dumps({"log": {"version": "1.2", "entries": [
            entry("GET", "https://api.example.com/ok", 200),
            entry("POST", "https://api.example.com/made", 201),
            entry("GET", "https://api.example.com/gone", 404),
            entry("PROPFIND", "https://api.example.com/dav", 207),
        ]}}), encoding="utf-8")

        out_dir = tmp_path / "out"
        MockGenerator(use_smart_fallback=False).generate_all(
            HARParser(str(har_path)).export_as_dict()["endpoints"],
            output_dir=str(out_dir),
        )

        data = json.loads(
            runner.invoke(app, ["stats", str(out_dir), "--json"]).stdout
        )
        assert data["total_endpoints"] == 4
        assert data["method_counts"]["PROPFIND"] == 1
        assert data["endpoints"]["POST /made"]["status_codes"] == ["201"]
        assert data["endpoints"]["GET /gone"]["status_codes"] == ["404"]
        assert data["endpoints"]["PROPFIND /dav"]["status_codes"] == ["207"]

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
