"""
MockClaw CLI Tool
Record, generate, and serve mock APIs from HAR files.
"""

import sys
import subprocess
import uvicorn
from pathlib import Path
from typing import Optional

import typer

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.parser import HARParser
from core.generator import MockGenerator

app = typer.Typer(
    name="mockclaw",
    help="MockClaw - Generate mock APIs from HAR files",
    add_completion=False,
    epilog="""
Examples:
  # Generate mock server from HAR file (no LLM required)
  $ mockclaw generate tests/gauntlet/flow.har generated_mocks --no-llm

  # Start mock server on custom port
  $ mockclaw serve generated_mocks --port 8080

  # Record user session from running API
  $ mockclaw record --url http://localhost:9000 --output my_traffic.har

  # Run chaos tests against mock server
  $ mockclaw test generated_mocks

  # Full workflow (5 minutes)
  $ mockclaw record -o traffic.har
  $ mockclaw generate traffic.har --no-llm
  $ mockclaw serve
  $ mockclaw test

Documentation: https://github.com/EternalRights/MockClaw/docs
    """,
)


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
      $ mockclaw record && mockclaw generate tests/gauntlet/flow.har --no-llm
    """
    typer.echo(f"🎙️  Starting recording from {url}...")
    
    # Check if Dummy Shop is running
    try:
        import requests
        resp = requests.get(f"{url}/health", timeout=3)
        if resp.status_code != 200:
            typer.echo(f"❌ Dummy Shop returned status {resp.status_code}")
            raise typer.Exit(1)
        typer.echo("✅ Dummy Shop is running")
    except requests.exceptions.ConnectionError:
        typer.echo("❌ Cannot connect to Dummy Shop!")
        typer.echo(f"\nPlease start Dummy Shop first:")
        typer.echo(f"  python tests/gauntlet/dummy_shop.py")
        raise typer.Exit(1)
    
    # Run recorder
    recorder_script = Path(__file__).parent.parent / "scripts" / "gauntlet_recorder.py"
    if not recorder_script.exists():
        typer.echo("❌ Gauntlet recorder script not found")
        raise typer.Exit(1)
    
    try:
        result = subprocess.run(
            [sys.executable, str(recorder_script)],
            cwd=Path.cwd(),
            capture_output=False,
            timeout=120,
        )
        
        if result.returncode == 0:
            typer.echo(f"\n✅ Recording complete: {output}")
        else:
            typer.echo(f"\n❌ Recording failed with code {result.returncode}")
            raise typer.Exit(1)
            
    except subprocess.TimeoutExpired:
        typer.echo("\n❌ Recording timed out")
        raise typer.Exit(1)


@app.command()
def generate(
    har_file: str = typer.Argument(
        ...,
        help="Path to HAR file",
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
      # Generate without LLM (recommended for testing)
      $ mockclaw generate tests/gauntlet/flow.har --no-llm
      
      # Custom output directory
      $ mockclaw generate traffic.har ./my_mocks --smart-fallback
      
      # Full generation with verbose output
      $ mockclaw generate flow.har -o mocks --no-llm && mockclaw serve mocks
    """
    har_path = Path(har_file)
    if not har_path.exists():
        typer.echo(f"❌ HAR file not found: {har_file}")
        raise typer.Exit(1)
    
    typer.echo(f"📦 Parsing HAR file: {har_file}")
    
    try:
        # Parse HAR
        parser = HARParser(str(har_path))
        endpoints_data = parser.export_as_dict()
        num_endpoints = len(endpoints_data.get("endpoints", []))
        typer.echo(f"✅ Found {num_endpoints} endpoints")
        
        # Generate mocks
        typer.echo(f"🤖 Generating mocks...")
        if no_llm or smart_fallback:
            typer.echo("   Mode: Smart Fallback (rule-based routing)")
            generator = MockGenerator(use_smart_fallback=True)
        else:
            typer.echo("   Mode: LLM-assisted (if API key configured)")
            generator = MockGenerator()
        
        results = generator.generate_all(
            endpoints_data["endpoints"],
            output_dir,
            use_smart_fallback=no_llm or smart_fallback,
        )
        
        # Report results
        success_count = sum(1 for r in results if r.success)
        typer.echo(f"\n✅ Generated {success_count}/{len(results)} endpoints")
        
        if success_count < len(results):
            typer.echo("\n⚠️  Some endpoints failed:")
            for r in results:
                if not r.success:
                    typer.echo(f"   - {r.endpoint_path}: {r.error}")
        
        typer.echo(f"\n📂 Output directory: {Path(output_dir).absolute()}")
        typer.echo(f"   Main file: {Path(output_dir) / 'dynamic_api.py'}")
        
    except Exception as e:
        typer.echo(f"❌ Generation failed: {e}")
        if typer.Option("verbose", "-v", "--verbose", default=False):
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
        help="Port to listen on",
    ),
    reload: bool = typer.Option(
        False,
        "--reload",
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
      $ mockclaw generate flow.har --no-llm && mockclaw serve
    """
    mock_path = Path(mock_dir) / "dynamic_api.py"
    if not mock_path.exists():
        typer.echo(f"❌ Mock file not found: {mock_path}")
        typer.echo(f"\nPlease generate mocks first:")
        typer.echo(f"  mockclaw generate tests/gauntlet/flow.har")
        raise typer.Exit(1)
    
    # Convert to module path (handle relative paths correctly)
    mock_path_obj = Path(mock_dir)
    if mock_path_obj.is_absolute():
        # For absolute paths, use the last parts
        module_path = f"{mock_path_obj.parts[-1]}.dynamic_api:app"
    else:
        # For relative paths, just clean up the separators
        clean_path = str(mock_path_obj).replace('\\', '.').replace('/', '.')
        module_path = f"{clean_path}.dynamic_api:app"
    
    typer.echo(f"🚀 Starting mock server...")
    typer.echo(f"   Module: {module_path}")
    typer.echo(f"   Host: {host}:{port}")
    typer.echo(f"   Reload: {reload}")
    
    # Check if port is available
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
        sock.close()
    except OSError:
        typer.echo(f"\n❌ Port {port} is already in use!")
        typer.echo(f"\nSolutions:")
        typer.echo(f"  1. Use a different port: mockclaw serve {mock_dir} --port 8001")
        typer.echo(f"  2. Find and stop the process using port {port}:")
        if sys.platform == 'win32':
            typer.echo(f"     netstat -ano | findstr :{port}")
            typer.echo(f"     taskkill /PID <PID> /F")
        else:
            typer.echo(f"     lsof -i :{port}")
            typer.echo(f"     kill -9 <PID>")
        raise typer.Exit(1)
    
    typer.echo(f"\n📖 API docs: http://{host.replace('0.0.0.0', 'localhost')}:{port}/docs")
    typer.echo(f"   Health: http://{host.replace('0.0.0.0', 'localhost')}:{port}/health")
    typer.echo(f"\nPress Ctrl+C to stop\n")
    
    try:
        uvicorn.run(
            module_path,
            host=host,
            port=port,
            reload=reload,
            log_level="info",
        )
    except KeyboardInterrupt:
        typer.echo("\n👋 Server stopped")
    except Exception as e:
        error_msg = str(e)
        if "Address already in use" in error_msg or "Only one usage of each socket address" in error_msg:
            typer.echo(f"\n❌ Port {port} is already in use!")
            typer.echo(f"\nSolutions:")
            typer.echo(f"  1. Use a different port: mockclaw serve {mock_dir} --port 8001")
            typer.echo(f"  2. Stop the existing server and try again")
        else:
            typer.echo(f"❌ Server error: {e}")
        raise typer.Exit(1)


@app.command()
def test(
    mock_dir: str = typer.Argument(
        "generated_mocks",
        help="Directory containing generated mocks",
    ),
    hardcore: bool = typer.Option(
        False,
        "--hardcore",
        help="Run hardcore chaos tests (requires Docker)",
    ),
):
    """
    Run chaos tests against mock server.
    
    Comprehensive adversarial testing including concurrency, garbage data,
    path traversal attacks, and rate limiting validation.
    
    Examples:
      # Run standard chaos tests (no Docker required)
      $ mockclaw test generated_mocks
      
      # Run hardcore tests with Docker (infrastructure sabotage)
      $ mockclaw test --hardcore
      
      # Quick validation after generation
      $ mockclaw generate flow.har --no-llm && mockclaw test
    """
    typer.echo(f"🥋 Running chaos tests...")
    
    if hardcore:
        test_script = Path(__file__).parent.parent / "scripts" / "hardcore_chaos_test.py"
    else:
        test_script = Path(__file__).parent.parent / "scripts" / "enhanced_chaos_test.py"
    
    if not test_script.exists():
        typer.echo(f"❌ Test script not found: {test_script}")
        raise typer.Exit(1)
    
    try:
        result = subprocess.run(
            [sys.executable, str(test_script)],
            cwd=Path.cwd(),
            capture_output=False,
            timeout=300,
        )
        
        if result.returncode == 0:
            typer.echo(f"\n✅ All chaos tests passed!")
        else:
            typer.echo(f"\n❌ Chaos tests failed with code {result.returncode}")
            raise typer.Exit(1)
            
    except subprocess.TimeoutExpired:
        typer.echo("\n❌ Chaos tests timed out")
        raise typer.Exit(1)


def main():
    """CLI entry point."""
    app()


if __name__ == "__main__":
    main()
