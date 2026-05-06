"""
MockClaw Brain Service - FastAPI Backend
Provides REST API for the dashboard.
"""

import os
import sys
import json
import hashlib
import tempfile
import time
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager
from datetime import datetime
import logging

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from core.parser import HARParser
from core.generator import MockGenerator

try:
    from importlib.metadata import version as _pkg_version
    APP_VERSION = _pkg_version("mockclaw")
except Exception:
    try:
        from mockclaw import __version__ as APP_VERSION
    except ImportError:
        APP_VERSION = "0.2.0"
START_TIME = time.time()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info(f"MockClaw Brain v{APP_VERSION} starting up...")
    llm_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not llm_key:
        logger.warning("LLM API key not configured. Mock generation will use smart fallback.")
    else:
        logger.info("LLM API key configured")
    yield
    logger.info("MockClaw Brain shutting down...")


app = FastAPI(
    title="MockClaw Brain",
    description="Mock API Generator Backend",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

generated_endpoints: dict[str, dict[str, Any]] = {}
generation_logs: list[dict[str, str]] = []
_MAX_LOG_ENTRIES = 1000


class HealthResponse(BaseModel):
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Application version")
    uptime: str = Field(..., description="Service uptime")
    services: dict[str, str] = Field(..., description="Service statuses")


class EndpointInfo(BaseModel):
    id: str = Field(..., description="Unique endpoint identifier")
    path: str = Field(..., description="API endpoint path")
    method: str = Field(..., description="HTTP method")
    status: int = Field(..., description="HTTP status code")
    generated: bool = Field(False, description="Whether mock is generated")
    hash: str | None = Field(None, description="Content hash for change detection")

    @validator('method')
    def validate_method(cls, v):
        allowed = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'}
        if v.upper() not in allowed:
            raise ValueError(f"Invalid HTTP method: {v}")
        return v.upper()


class GenerateRequest(BaseModel):
    endpoint_id: str = Field(..., min_length=1, description="Endpoint to generate")


class ParseResponse(BaseModel):
    total_endpoints: int = Field(..., description="Number of endpoints found")
    endpoints: list[EndpointInfo] = Field(..., description="Parsed endpoints")
    processing_time_ms: int = Field(..., description="Processing duration")


def compute_endpoint_hash(endpoint_data: dict[str, Any]) -> str:
    content = json.dumps(endpoint_data, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_uptime() -> str:
    elapsed = time.time() - START_TIME
    hours, remainder = divmod(int(elapsed), 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def check_services() -> dict[str, str]:
    services = {
        "backend": "running",
        "docker": "unknown",
        "llm": "not_configured"
    }
    try:
        import docker
        client = docker.from_env(timeout=5)
        client.ping()
        services["docker"] = "running"
    except Exception:
        services["docker"] = "not_available"
    llm_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if llm_key:
        services["llm"] = "configured"
    return services


@app.exception_handler(json.JSONDecodeError)
async def json_decode_error(request: Request, exc: json.JSONDecodeError):
    logger.error(f"JSON decode error: {exc}")
    return JSONResponse(status_code=400, content={"detail": "Invalid JSON in request body"})


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})


@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        uptime=get_uptime(),
        services=check_services()
    )


@app.get("/mockclaw/info", tags=["System"])
async def mockclaw_info():
    return {
        "generator": "MockClaw",
        "version": APP_VERSION,
        "endpoints": list(generated_endpoints.keys()),
        "total_generated": len([e for e in generated_endpoints.values() if e.get("generated")]),
        "uptime": get_uptime()
    }


@app.post("/parse", response_model=ParseResponse, tags=["Parsing"])
async def parse_har_file(file: UploadFile = File(...)):
    start_time = time.time()

    if not file.filename or not file.filename.endswith('.har'):
        raise HTTPException(status_code=400, detail="File must have .har extension")

    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")

    try:
        json.loads(content.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid file: {e}")

    with tempfile.NamedTemporaryFile(suffix=".har", delete=False) as tmp:
        temp_path = Path(tmp.name)
        tmp.write(content)

    try:
        parser = HARParser(str(temp_path))
        endpoints_data = parser.export_as_dict()

        generated_endpoints.clear()

        result_endpoints = []
        for i, ep_data in enumerate(endpoints_data["endpoints"]):
            endpoint_id = f"ep_{i}"
            ep_data["id"] = endpoint_id
            ep_data["hash"] = compute_endpoint_hash(ep_data)

            generated_endpoints[endpoint_id] = ep_data

            result_endpoints.append(EndpointInfo(
                id=endpoint_id,
                path=ep_data["resource_path"],
                method=ep_data["method"],
                status=ep_data.get("sample_response", {}).get("status", 200),
                generated=False,
                hash=ep_data["hash"]
            ))

        processing_time = int((time.time() - start_time) * 1000)

        return ParseResponse(
            total_endpoints=endpoints_data["total_endpoints"],
            endpoints=result_endpoints,
            processing_time_ms=processing_time
        )

    except Exception as e:
        logger.exception(f"Parse error: {e}")
        raise HTTPException(status_code=500, detail=f"Parse error: {str(e)}")
    finally:
        temp_path.unlink(missing_ok=True)


@app.post("/generate", tags=["Generation"])
async def generate_mock(request: GenerateRequest):
    endpoint_id = request.endpoint_id

    if endpoint_id not in generated_endpoints:
        raise HTTPException(status_code=404, detail=f"Endpoint not found: {endpoint_id}")

    endpoint = generated_endpoints[endpoint_id]

    if endpoint.get("generated"):
        return {
            "success": True,
            "endpoint_id": endpoint_id,
            "cached": True,
            "message": "Endpoint already generated"
        }

    logs = [
        {"timestamp": datetime.now().isoformat(), "level": "info",
         "message": f"Starting generation for {endpoint['method']} {endpoint['resource_path']}"},
        {"timestamp": datetime.now().isoformat(), "level": "info",
         "message": "Generating mock code..."},
    ]

    result = None
    try:
        generator = MockGenerator(use_smart_fallback=True)
        result = generator.generate_endpoint(endpoint)

        if result.success:
            logs.append({"timestamp": datetime.now().isoformat(), "level": "success",
                         "message": f"Generated mock for {endpoint['method']} {endpoint['resource_path']}"})
        else:
            logs.append({"timestamp": datetime.now().isoformat(), "level": "error",
                         "message": f"Generation failed: {result.error}"})
    except Exception as e:
        logs.append({"timestamp": datetime.now().isoformat(), "level": "error",
                     "message": f"Generation error: {e}"})

    succeeded = result is not None and result.success
    if succeeded:
        generated_endpoints[endpoint_id]["generated"] = True
        generated_endpoints[endpoint_id]["generated_at"] = datetime.now().isoformat()
        generated_endpoints[endpoint_id]["generated_code"] = result.generated_code

    generation_logs.extend(logs)
    if len(generation_logs) > _MAX_LOG_ENTRIES:
        generation_logs[:] = generation_logs[-_MAX_LOG_ENTRIES:]

    logger.info(f"Generated mock for endpoint: {endpoint_id} (success={succeeded})")

    return {
        "success": succeeded,
        "endpoint_id": endpoint_id,
        "cached": False,
        "logs": logs,
        "generated_code": result.generated_code if succeeded else None,
        "error": result.error if result and not result.success else None,
    }


@app.get("/logs", tags=["System"])
async def get_logs(limit: int = 100):
    return {"logs": generation_logs[-limit:]}


@app.delete("/logs", tags=["System"])
async def clear_logs():
    generation_logs.clear()
    logger.info("Logs cleared")
    return {"success": True}


@app.get("/endpoints", tags=["Endpoints"])
async def list_endpoints():
    return {
        "total": len(generated_endpoints),
        "endpoints": list(generated_endpoints.values())
    }


@app.delete("/endpoints/{endpoint_id}", tags=["Endpoints"])
async def delete_endpoint(endpoint_id: str):
    if endpoint_id not in generated_endpoints:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    del generated_endpoints[endpoint_id]

    logger.info(f"Deleted endpoint: {endpoint_id}")
    return {"success": True}


@app.post("/generate-all", tags=["Generation"])
async def generate_all_endpoints():
    results = []

    for endpoint_id, endpoint in generated_endpoints.items():
        if not endpoint.get("generated"):
            result = await generate_mock(GenerateRequest(endpoint_id=endpoint_id))
            results.append(result)

    successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))

    logger.info(f"Batch generation complete: {successful}/{len(results)}")

    return {
        "success": True,
        "generated_count": successful,
        "total_attempted": len(results)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
