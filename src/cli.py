"""
MockClaw CLI Tool
Record, generate, and serve mock APIs from HAR files.
"""

import sys
import socket
import subprocess
import uvicorn
import shutil
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

Documentation: https://github.com/EternalRights/MockClaw/docs
    """,
)


def version_callback(value: bool):
    if value:
        console.print("[bold cyan]MockClaw[/bold cyan] version [bold]0.2.0[/bold]")
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
    
    This command creates a complete example from the sample HAR file,
    generates the mock server, and starts it for immediate testing.
    
    Perfect for first-time users to see MockClaw in action!
    """
    console.print("\n[bold cyan]🚀 MockClaw Quick Start[/bold cyan]\n")
    
    sample_har = Path(__file__).parent.parent / "examples" / "sample.har"
    
    if not sample_har.exists():
        console.print("[red]❌ Sample HAR file not found![/red]")
        console.print("\n[yellow]Creating sample HAR file...[/yellow]")
        
        examples_dir = Path(__file__).parent.parent / "examples"
        examples_dir.mkdir(exist_ok=True)
        
        test_har = Path(__file__).parent.parent / "tests" / "gauntlet" / "flow.har"
        if test_har.exists():
            shutil.copy(test_har, sample_har)
            console.print("[green]✅ Sample HAR file created[/green]")
        else:
            console.print("[red]❌ No sample HAR file available[/red]")
            console.print("\n[yellow]Please run the following commands first:[/yellow]")
            console.print("  1. python tests/gauntlet/dummy_shop.py &")
            console.print("  2. python scripts/gauntlet_recorder.py")
            raise typer.Exit(1)
    
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        console=console,
    ) as progress:
        task1 = progress.add_task("[cyan]Parsing HAR file...", total=None)
        
        try:
            parser = HARParser(str(sample_har))
            endpoints_data = parser.export_as_dict()
            num_endpoints = len(endpoints_data.get("endpoints", []))
            progress.update(task1, description=f"[green]✅ Found {num_endpoints} endpoints[/green]")
        except Exception as e:
            console.print(f"[red]❌ Failed to parse HAR file: {e}[/red]")
            raise typer.Exit(1)
        
        task2 = progress.add_task("[cyan]Generating mock server...", total=None)
        
        try:
            generator = MockGenerator(use_smart_fallback=True)
            results = generator.generate_all(
                endpoints_data["endpoints"],
                output_dir,
                use_smart_fallback=True,
            )
            success_count = sum(1 for r in results if r.success)
            progress.update(task2, description=f"[green]✅ Generated {success_count}/{len(results)} endpoints[/green]")
        except Exception as e:
            console.print(f"[red]❌ Failed to generate mocks: {e}[/red]")
            raise typer.Exit(1)
    
    console.print(f"\n[bold green]✅ Mock server ready![/bold green]")
    console.print(f"\n[bold]Next steps:[/bold]")
    console.print(f"  1. Start the server: [cyan]mockclaw serve {output_dir} --port {port}[/cyan]")
    console.print(f"  2. Open API docs: [cyan]http://localhost:{port}/docs[/cyan]")
    console.print(f"  3. Test health: [cyan]curl http://localhost:{port}/health[/cyan]")
    
    console.print(f"\n[bold]Test scenarios:[/bold]")
    console.print(f"  # Expired coupon (returns 400):")
    console.print(f'  [dim]curl -X POST http://localhost:{port}/checkout -H "Content-Type: application/json" -d \'{{"user_id":"test","coupon_code":"EXPIRED2026"}}\'[/dim]')
    console.print(f"\n  # Valid coupon (returns success):")
    console.print(f'  [dim]curl -X POST http://localhost:{port}/checkout -H "Content-Type: application/json" -d \'{{"user_id":"test","coupon_code":"SAVE10"}}\'[/dim]')


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
        help="Disable LLM, use smart fallback routing",
    ),
    smart_fallback: bool = typer.Option(
        False,
        "--smart-fallback",
        help="Enable smart conditional routing based on request body",
    ),
):
    """
    Generate mock API server from HAR file.
    
    Parses HAR file and generates FastAPI mock endpoints with auto-injected
    resilience middleware (path traversal protection, rate limiting, error handling).
    
    Use --no-llm or --smart-fallback for rule-based routing without API keys.
    
    Examples:
      # Generate from sample HAR (recommended for first-time users)
      $ mockclaw generate examples/sample.har ./my_mocks --smart-fallback
      
      # Generate without LLM (recommended for testing)
      $ mockclaw generate tests/gauntlet/flow.har --no-llm
      
      # Custom output directory
      $ mockclaw generate traffic.har ./my_mocks --smart-fallback
      
      # Full generation with verbose output
      $ mockclaw generate flow.har -o mocks --no-llm && mockclaw serve mocks
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
            
            if no_llm or smart_fallback:
                mode = "Smart Fallback (rule-based routing)"
                generator = MockGenerator(use_smart_fallback=True)
            else:
                mode = "LLM-assisted (if API key configured)"
                generator = MockGenerator()
            
            console.print(f"\n[dim]   Mode: {mode}[/dim]")
            
            results = generator.generate_all(
                endpoints_data["endpoints"],
                output_dir,
                use_smart_fallback=no_llm or smart_fallback,
            )
            
            success_count = sum(1 for r in results if r.success)
            progress.update(task2, description=f"[green]✅ Generated {success_count}/{len(results)} endpoints[/green]")
            
            if success_count < len(results):
                console.print("\n[yellow]⚠️  Some endpoints failed:[/yellow]")
                for r in results:
                    if not r.success:
                        console.print(f"   [red]• {r.endpoint_path}: {r.error}[/red]")
        
        console.print(f"\n[bold green]✅ Mock server generated successfully![/bold green]")
        console.print(f"\n[bold]Output:[bold]")
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
    
    mock_path_obj = Path(mock_dir)
    if mock_path_obj.is_absolute():
        module_path = f"{mock_path_obj.parts[-1]}.dynamic_api:app"
    else:
        clean_path = str(mock_path_obj).replace('\\', '.').replace('/', '.')
        module_path = f"{clean_path}.dynamic_api:app"
    
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
            [sys.executable, str(test_script)],
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
def info():
    """
    Show system information and configuration.
    
    Displays Python version, installed packages, and environment details
    useful for debugging and troubleshooting.
    """
    console.print("\n[bold cyan]MockClaw System Information[/bold cyan]\n")
    
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Component", style="bold")
    table.add_column("Version/Info", style="green")
    
    table.add_row("MockClaw", "0.2.0")
    table.add_row("Python", f"{sys.version}")
    table.add_row("Platform", sys.platform)
    table.add_row("Working Directory", str(Path.cwd()))
    
    try:
        import fastapi
        table.add_row("FastAPI", fastapi.__version__)
    except ImportError:
        table.add_row("FastAPI", "[red]Not installed[/red]")
    
    try:
        import uvicorn
        table.add_row("Uvicorn", uvicorn.__version__)
    except ImportError:
        table.add_row("Uvicorn", "[red]Not installed[/red]")
    
    try:
        import typer
        table.add_row("Typer", typer.__version__)
    except ImportError:
        table.add_row("Typer", "[red]Not installed[/red]")
    
    console.print(table)
    
    console.print("\n[bold]Environment Variables:[/bold]")
    import os
    openai_key = os.getenv("OPENAI_API_KEY")
    if openai_key:
        console.print(f"  OPENAI_API_KEY: [green]{'*' * 8}{openai_key[-4:]}[/green]")
    else:
        console.print(f"  OPENAI_API_KEY: [yellow]Not set (optional)[/yellow]")


if __name__ == "__main__":
    app()
