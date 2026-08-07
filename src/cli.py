"""
MockClaw CLI Tool
Record, generate, and serve mock APIs from HAR files.
"""

import sys
import re
import socket
import subprocess
import uvicorn
from collections import Counter
from pathlib import Path

import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

if sys.version_info < (3, 11):
    print("Error: MockClaw requires Python 3.11 or higher")
    print(f"Current version: {sys.version}")
    print("\nPlease upgrade Python and try again.")
    sys.exit(1)

sys.path.insert(0, str(Path(__file__).parent))

from core.parser import HARParser
from core.generator import MockGenerator
from _version import get_version

__version__ = get_version()

console = Console()

app = typer.Typer(
    name="mockclaw",
    help="MockClaw - Generate mock APIs from HAR files",
    add_completion=False,
    epilog="""
Examples:
  # Quick start with sample HAR
  $ mockclaw example

  # Generate mock server from HAR file (no LLM required)
  $ mockclaw generate examples/sample.har generated_mocks --smart-fallback

  # Start mock server on custom port
  $ mockclaw serve generated_mocks --port 8080

  # Record user session from running API
  $ mockclaw record --url http://localhost:9000 --output my_traffic.har

  # Run chaos tests against mock server
  $ mockclaw test generated_mocks

  # Show mock server statistics
  $ mockclaw stats generated_mocks

Documentation: https://github.com/EternalRights/MockClaw/docs
    """,
)


def version_callback(value: bool):
    if value:
        console.print(f"[bold cyan]MockClaw[/bold cyan] version [bold]{__version__}[/bold]")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        "-v",
        callback=version_callback,
        is_eager=True,
        help="Show version and exit",
    ),
):
    """
    MockClaw - Turn production traffic into testable mock servers in under 2 minutes.
    """
    pass


@app.command()
def example(
    output_dir: str = typer.Option(
        "example_mocks",
        "--output",
        "-o",
        help="Output directory for generated mocks",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port for the mock server",
    ),
):
    """
    Quick start: Generate and serve a sample mock server.
    
    Uses the bundled sample HAR file to generate a working mock server
    with no additional setup required.
    """
    console.print("\n[bold cyan]MockClaw Quick Start[/bold cyan]\n")
    
    sample_har = Path(__file__).parent.parent / "examples" / "sample.har"
    
    if not sample_har.exists():
        console.print("[red]Sample HAR file not found![/red]")
        console.print(f"Expected at: {sample_har}")
        raise typer.Exit(1)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task1 = progress.add_task("Parsing HAR file...", total=None)
        
        try:
            parser = HARParser(str(sample_har))
            endpoints_data = parser.export_as_dict()
            num_endpoints = len(endpoints_data.get("endpoints", []))
            progress.update(task1, description=f"Found {num_endpoints} endpoints")
        except Exception as e:
            console.print(f"Failed to parse HAR file: {e}")
            raise typer.Exit(1)
        
        task2 = progress.add_task("Generating mock server...", total=None)
        
        try:
            generator = MockGenerator(use_smart_fallback=True)
            results = generator.generate_all(
                endpoints_data["endpoints"],
                output_dir,
                use_smart_fallback=True,
            )
            success_count = sum(1 for r in results if r.success)
            progress.update(task2, description=f"Generated {success_count}/{len(results)} endpoints")
        except Exception as e:
            console.print(f"Failed to generate mocks: {e}")
            raise typer.Exit(1)
    
    console.print(f"\nMock server ready!")
    console.print(f"\nNext steps:")
    console.print(f"  1. Start the server: [cyan]mockclaw serve {output_dir} --port {port}[/cyan]")
    console.print(f"  2. Open API docs: [cyan]http://localhost:{port}/docs[/cyan]")
    console.print(f"  3. Test health: [cyan]curl http://localhost:{port}/health[/cyan]")


@app.command()
def record(
    output: str = typer.Option(
        "tests/gauntlet/flow.har",
        "--output", "-o",
        help="Output path for HAR file",
    ),
    url: str = typer.Option(
        "http://localhost:9000",
        "--url", "-u",
        help="Base URL to record from",
    ),
):
    """
    Record user sessions and generate HAR file.
    
    Runs the gauntlet recorder to capture API traffic from a running service.
    
    Examples:
      # Record from local Dummy Shop
      $ mockclaw record --url http://localhost:9000
      
      # Save to custom location
      $ mockclaw record -o my_session.har
      
      # Full workflow
      $ mockclaw record && mockclaw generate tests/gauntlet/flow.har --smart-fallback
    """
    console.print(f"\n[cyan]🎙️  Starting recording from {url}...[/cyan]\n")
    
    try:
        import requests
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Checking Dummy Shop...", total=None)
            resp = requests.get(f"{url}/health", timeout=3)
            if resp.status_code != 200:
                console.print(f"[red]❌ Dummy Shop returned status {resp.status_code}[/red]")
                raise typer.Exit(1)
            progress.update(task, description="[green]✅ Dummy Shop is running[/green]")
    except requests.exceptions.ConnectionError:
        console.print("[red]❌ Cannot connect to Dummy Shop![/red]")
        console.print("\n[yellow]Please start Dummy Shop first:[/yellow]")
        console.print("  [cyan]python tests/gauntlet/dummy_shop.py[/cyan]")
        raise typer.Exit(1)
    
    recorder_script = Path(__file__).parent.parent / "scripts" / "gauntlet_recorder.py"
    if not recorder_script.exists():
        console.print("[red]❌ Gauntlet recorder script not found[/red]")
        raise typer.Exit(1)
    
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("gauntlet_recorder", recorder_script)
        recorder_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(recorder_module)
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task = progress.add_task("[cyan]Recording user session...", total=None)
            
            recorder = recorder_module.GauntletRecorder(url)
            recorder.run_user_session()
            har_path = recorder.export_har(output)
            
            progress.update(task, description="[green]✅ Recording complete[/green]")
        
        console.print(f"\n[green]✅ HAR file saved: {har_path}[/green]")
        
    except Exception as e:
        console.print(f"\n[red]❌ Recording failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def generate(
    har_file: str = typer.Argument(
        ...,
        help="Path to HAR file (or use 'examples/sample.har' for quick start)",
    ),
    output_dir: str = typer.Argument(
        "generated_mocks",
        help="Output directory for generated mocks",
    ),
    no_llm: bool = typer.Option(
        False,
        "--no-llm",
        help="Disable LLM, use simple template fallback (no smart routing)",
    ),
    smart_fallback: bool = typer.Option(
        False,
        "--smart-fallback",
        help="Enable smart conditional routing based on request body analysis",
    ),
):
    """
    Generate mock API server from HAR file.
    
    Parses HAR file and generates FastAPI mock endpoints with auto-injected
    resilience middleware (path traversal protection, rate limiting, error handling).
    
    Modes:
      - Default: LLM-assisted if API key configured, otherwise template fallback
      - --no-llm: Simple template fallback (returns HAR response as-is)
      - --smart-fallback: Smart routing based on request body field analysis
    
    Examples:
      # Generate from sample HAR (recommended for first-time users)
      $ mockclaw generate examples/sample.har ./my_mocks --smart-fallback
      
      # Generate without LLM (simple template mode)
      $ mockclaw generate tests/gauntlet/flow.har --no-llm
      
      # Custom output directory
      $ mockclaw generate traffic.har ./my_mocks --smart-fallback
    """
    har_path = Path(har_file)
    if not har_path.exists():
        console.print(f"[red]❌ HAR file not found: {har_file}[/red]")
        console.print("\n[yellow]Suggestions:[/yellow]")
        
        sample_har = Path(__file__).parent.parent / "examples" / "sample.har"
        if sample_har.exists():
            console.print(f"  • Use sample HAR: [cyan]mockclaw generate examples/sample.har {output_dir} --smart-fallback[/cyan]")
        else:
            console.print(f"  • Generate sample: [cyan]mockclaw example[/cyan]")
        
        console.print(f"  • Record your own: [cyan]mockclaw record[/cyan]")
        raise typer.Exit(1)
    
    console.print(f"\n[cyan]📦 Parsing HAR file: {har_file}[/cyan]")
    
    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            console=console,
        ) as progress:
            task1 = progress.add_task("[cyan]Parsing HAR file...", total=None)
            
            parser = HARParser(str(har_path))
            endpoints_data = parser.export_as_dict()
            num_endpoints = len(endpoints_data.get("endpoints", []))
            
            progress.update(task1, description=f"[green]✅ Found {num_endpoints} endpoints[/green]")
            
            task2 = progress.add_task("[cyan]Generating mocks...", total=None)
            
            if no_llm:
                mode = "Template Fallback (simple, no smart routing)"
                generator = MockGenerator(use_smart_fallback=False)
            elif smart_fallback:
                mode = "Smart Fallback (rule-based routing)"
                generator = MockGenerator(use_smart_fallback=True)
            else:
                mode = "LLM-assisted (if API key configured)"
                generator = MockGenerator()
            
            console.print(f"\n[dim]   Mode: {mode}[/dim]")
            
            results = generator.generate_all(
                endpoints_data["endpoints"],
                output_dir,
            )
            
            success_count = sum(1 for r in results if r.success)
            progress.update(task2, description=f"[green]✅ Generated {success_count}/{len(results)} endpoints[/green]")
            
            if success_count < len(results):
                console.print("\n[yellow]⚠️  Some endpoints failed:[/yellow]")
                for r in results:
                    if not r.success:
                        console.print(f"   [red]• {r.endpoint_path}: {r.error}[/red]")
        
        console.print(f"\n[bold green]✅ Mock server generated successfully![/bold green]")
        console.print(f"\n[bold]Output:[/bold]")
        console.print(f"  📂 Directory: [cyan]{Path(output_dir).absolute()}[/cyan]")
        console.print(f"  📄 Main file: [cyan]{Path(output_dir) / 'dynamic_api.py'}[/cyan]")
        
        console.print(f"\n[bold]Next steps:[/bold]")
        console.print(f"  1. Start server: [cyan]mockclaw serve {output_dir}[/cyan]")
        console.print(f"  2. View API docs: [cyan]http://localhost:8000/docs[/cyan]")
        
    except Exception as e:
        console.print(f"[red]❌ Generation failed: {e}[/red]")
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def serve(
    mock_dir: str = typer.Argument(
        "generated_mocks",
        help="Directory containing generated mocks",
    ),
    host: str = typer.Option(
        "0.0.0.0",
        "--host",
        help="Host to bind to",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        "-p",
        help="Port to listen on",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
        "-r",
        help="Enable auto-reload (development mode)",
    ),
):
    """
    Start mock API server.
    
    Runs the generated FastAPI application with uvicorn.
    Server includes auto-generated OpenAPI docs at /docs endpoint.
    
    Examples:
      # Start server on default port 8000
      $ mockclaw serve generated_mocks
      
      # Custom port for development
      $ mockclaw serve --port 8080 --reload
      
      # Production deployment
      $ mockclaw serve --host 0.0.0.0 --port 80
      
      # Quick start after generation
      $ mockclaw generate flow.har --smart-fallback && mockclaw serve
    """
    mock_path = Path(mock_dir) / "dynamic_api.py"
    if not mock_path.exists():
        console.print(f"[red]❌ Mock file not found: {mock_path}[/red]")
        console.print("\n[yellow]Please generate mocks first:[/yellow]")
        console.print(f"  [cyan]mockclaw generate examples/sample.har {mock_dir} --smart-fallback[/cyan]")
        raise typer.Exit(1)

    mock_dir_resolved = Path(mock_dir).resolve()
    module_path = f"{mock_dir_resolved.name}.dynamic_api:app"

    console.print(f"\n[bold cyan]🚀 Starting mock server...[/bold cyan]")
    
    table = Table(show_header=False, box=None)
    table.add_column("key", style="bold")
    table.add_column("value", style="cyan")
    table.add_row("Module", module_path)
    table.add_row("Host", f"{host}:{port}")
    table.add_row("Reload", str(reload))
    console.print(table)
    
    test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        test_sock.settimeout(1.0)
        result = test_sock.connect_ex((host.replace('0.0.0.0', '127.0.0.1'), port))
        test_sock.close()
        if result == 0:
            console.print(f"\n[red]❌ Port {port} is already in use![/red]")
            console.print("\n[yellow]Solutions:[/yellow]")
            console.print(f"  1. Use a different port: [cyan]mockclaw serve {mock_dir} --port 8001[/cyan]")
            console.print(f"  2. Find and stop the process using port {port}:")
            if sys.platform == 'win32':
                console.print(f"     [dim]netstat -ano | findstr :{port}[/dim]")
                console.print(f"     [dim]taskkill /PID <PID> /F[/dim]")
            else:
                console.print(f"     [dim]lsof -i :{port}[/dim]")
                console.print(f"     [dim]kill -9 <PID>[/dim]")
            raise typer.Exit(1)
    except Exception:
        test_sock.close()
    
    console.print(f"\n[bold]Endpoints:[/bold]")
    console.print(f"  📖 API docs: [cyan]http://{host.replace('0.0.0.0', 'localhost')}:{port}/docs[/cyan]")
    console.print(f"  ❤️  Health: [cyan]http://{host.replace('0.0.0.0', 'localhost')}:{port}/health[/cyan]")
    console.print(f"\n[dim]Press Ctrl+C to stop[/dim]\n")
    
    try:
        parent_dir = str(mock_dir_resolved.parent)
        if parent_dir not in sys.path:
            sys.path.insert(0, parent_dir)
        uvicorn.run(
            module_path,
            host=host,
            port=port,
            reload=reload,
            log_level="info",
        )
    except KeyboardInterrupt:
        console.print("\n[yellow]👋 Server stopped[/yellow]")
    except Exception as e:
        error_msg = str(e)
        if "Address already in use" in error_msg or "Only one usage of each socket address" in error_msg:
            console.print(f"\n[red]❌ Port {port} is already in use![/red]")
            console.print("\n[yellow]Solutions:[/yellow]")
            console.print(f"  1. Use a different port: [cyan]mockclaw serve {mock_dir} --port 8001[/cyan]")
            console.print(f"  2. Stop the existing server and try again")
        else:
            console.print(f"[red]❌ Server error: {e}[/red]")
        raise typer.Exit(1)


@app.command()
def test(
    mock_dir: str = typer.Argument(
        "generated_mocks",
        help="Directory containing generated mocks",
    ),
):
    """
    Run chaos tests against mock server.
    
    Comprehensive adversarial testing including concurrency, garbage data,
    path traversal attacks, and rate limiting validation.
    
    Examples:
      # Run chaos tests
      $ mockclaw test generated_mocks
      
      # Quick validation after generation
      $ mockclaw generate flow.har --smart-fallback && mockclaw test
    """
    console.print(f"\n[cyan]Running chaos tests...[/cyan]\n")
    
    test_script = Path(__file__).parent.parent / "scripts" / "enhanced_chaos_test.py"
    
    if not test_script.exists():
        console.print(f"[red]Test script not found: {test_script}[/red]")
        raise typer.Exit(1)
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_script), mock_dir],
            cwd=Path.cwd(),
            capture_output=False,
            timeout=300,
        )
        
        if result.returncode == 0:
            console.print(f"\n[green]All chaos tests passed![/green]")
        else:
            console.print(f"\n[red]Chaos tests failed with code {result.returncode}[/red]")
            raise typer.Exit(1)
            
    except subprocess.TimeoutExpired:
        console.print("\n[red]Chaos tests timed out[/red]")
        raise typer.Exit(1)


@app.command()
def info(
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output in JSON format (machine-readable)",
    ),
):
    """
    Show system information and configuration.
    
    Displays Python version, installed packages, and environment details
    useful for debugging and troubleshooting. Use --json for
    machine-readable output.
    """
    import os

    info_data = {
        "mockclaw": __version__,
        "python": {
            "version": sys.version,
            "platform": sys.platform,
        },
        "working_directory": str(Path.cwd()),
        "dependencies": {},
        "environment": {},
    }

    for pkg_name, import_name in [
        ("fastapi", "fastapi"),
        ("uvicorn", "uvicorn"),
        ("typer", "typer"),
        ("httpx", "httpx"),
        ("rich", "rich"),
        ("orjson", "orjson"),
    ]:
        try:
            mod = __import__(import_name)
            info_data["dependencies"][pkg_name] = getattr(mod, "__version__", "unknown")
        except ImportError:
            info_data["dependencies"][pkg_name] = None

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        info_data["environment"]["OPENAI_API_KEY"] = f"{'*' * 8}{openai_key[-4:]}"
    else:
        info_data["environment"]["OPENAI_API_KEY"] = None

    if json_output:
        console.print_json(data=info_data)
        return

    console.print("\n[bold cyan]MockClaw System Information[/bold cyan]\n")

    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Component", style="bold")
    table.add_column("Version/Info", style="green")

    table.add_row("MockClaw", __version__)
    table.add_row("Python", sys.version)
    table.add_row("Platform", sys.platform)
    table.add_row("Working Directory", str(Path.cwd()))

    for pkg_name, ver in info_data["dependencies"].items():
        display_name = pkg_name.capitalize() if pkg_name != "httpx" else "HTTPX"
        if ver:
            table.add_row(display_name, ver)
        else:
            table.add_row(display_name, "[red]Not installed[/red]")

    console.print(table)

    console.print("\n[bold]Environment Variables:[/bold]")
    if openai_key:
        console.print(f"  OPENAI_API_KEY: [green]{'*' * 8}{openai_key[-4:]}[/green]")
    else:
        console.print(f"  OPENAI_API_KEY: [yellow]Not set (optional)[/yellow]")


@app.command()
def stats(
    mock_dir: str = typer.Argument(
        "generated_mocks",
        help="Directory containing generated mocks",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        "-j",
        help="Output in JSON format (machine-readable)",
    ),
):
    """
    Show statistics about a generated mock server.

    Analyzes the generated FastAPI code to show endpoint counts,
    HTTP method distribution, routing complexity, and status code
    breakdown.

    Examples:
      $ mockclaw stats generated_mocks
      $ mockclaw stats generated_mocks --json
    """
    mock_path = Path(mock_dir) / "dynamic_api.py"
    if not mock_path.exists():
        console.print(f"[red]Mock file not found: {mock_path}[/red]")
        console.print("\n[yellow]Generate mocks first:[/yellow]")
        console.print(
            f"  [cyan]mockclaw generate examples/sample.har {mock_dir} --smart-fallback[/cyan]"
        )
        raise typer.Exit(1)

    content = mock_path.read_text(encoding="utf-8")
    _BUILTIN = {"health", "mockclaw/info"}

    decorator_pat = re.compile(r'@app\.(\w+)\("([^"]+)"\)')
    error_pat = re.compile(r"raise HTTPException\(status_code=status\.(\w+)")

    # Phase 1: discover endpoints
    endpoints: list[dict] = []
    for line in content.splitlines():
        m = decorator_pat.search(line)
        if not m:
            continue
        method, path = m.group(1).upper(), m.group(2)
        if path.strip("/") in _BUILTIN:
            continue
        endpoints.append({"method": method, "path": path})

    if not endpoints:
        console.print("[yellow]No generated endpoints found.[/yellow]")
        return

    # Phase 2: analyze each endpoint's block for routing type and status codes
    for ep in endpoints:
        marker = f'@app.{ep["method"].lower()}("{ep["path"]}")'
        pos = content.find(marker)
        block = content[pos : pos + 800] if pos >= 0 else ""

        ep["smart"] = "request: Request" in block[:500]

        statuses = [m.group(1) for m in error_pat.finditer(block[:500])]
        if not statuses:
            statuses = ["200_OK"]
        ep["status_codes"] = statuses

    # Phase 3: aggregate
    method_counts = Counter(ep["method"] for ep in endpoints)
    smart_count = sum(1 for ep in endpoints if ep["smart"])
    all_statuses = Counter()
    for ep in endpoints:
        all_statuses.update(ep["status_codes"])

    result = {
        "file": str(mock_path),
        "file_size_bytes": mock_path.stat().st_size,
        "total_endpoints": len(endpoints),
        "method_counts": dict(method_counts),
        "smart_routing_count": smart_count,
        "simple_routing_count": len(endpoints) - smart_count,
        "status_codes": dict(all_statuses),
    }

    if json_output:
        result["endpoints"] = {
            f'{ep["method"]} {ep["path"]}': {
                "smart": ep["smart"],
                "status_codes": ep["status_codes"],
            }
            for ep in endpoints
        }
        console.print_json(data=result)
        return

    console.print("\n[bold cyan]Mock Server Statistics[/bold cyan]\n")

    info_table = Table(show_header=False, box=None)
    info_table.add_column("Key", style="bold")
    info_table.add_column("Value", style="cyan")
    info_table.add_row("File", str(mock_path))
    info_table.add_row("Size", f"{result['file_size_bytes']:,} bytes")
    info_table.add_row("Total Endpoints", str(result["total_endpoints"]))
    console.print(info_table)

    console.print("\n[bold]HTTP Methods:[/bold]")
    method_table = Table(show_header=True, header_style="bold cyan")
    method_table.add_column("Method", style="bold")
    method_table.add_column("Count", justify="right")
    for method, count in sorted(method_counts.items()):
        method_table.add_row(method, str(count))
    console.print(method_table)

    console.print("\n[bold]Routing:[/bold]")
    route_table = Table(show_header=True, header_style="bold cyan")
    route_table.add_column("Type", style="bold")
    route_table.add_column("Count", justify="right")
    route_table.add_row("[green]Smart[/green]", str(smart_count))
    route_table.add_row("[dim]Simple[/dim]", str(result["simple_routing_count"]))
    console.print(route_table)

    if all_statuses:
        console.print("\n[bold]Response Statuses:[/bold]")
        status_table = Table(show_header=True, header_style="bold cyan")
        status_table.add_column("Status", style="bold")
        status_table.add_column("Count", justify="right")
        for status, count in sorted(all_statuses.items()):
            if "200" in status or "201" in status:
                color = "green"
            elif "400" in status or "401" in status or "403" in status or "404" in status:
                color = "yellow"
            else:
                color = "red"
            status_table.add_row(f"[{color}]{status}[/{color}]", str(count))
        console.print(status_table)


if __name__ == "__main__":
    app()
