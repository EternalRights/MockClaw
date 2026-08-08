"""
MockClaw Brain Service - FastAPI Backend
Provides REST API for the dashboard.
"""

import os
import sys
import json
import tempfile
import time
import asyncio
from pathlib import Path
from typing import Any
from contextlib import asynccontextmanager
from datetime import datetime
import logging

if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi import FastAPI, UploadFile, File, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname) - %(message)s'
)
logger = logging.getLogger(__name__)

sys.path.insert(0, str(Path(__file__).parent))

from core.parser import HARParser
from core.generator import MockGenerator
from _version import get_version

APP_VERSION = get_version()
START_TIME = time.time()


class AppState:
    """Centralized application state management.

    Encapsulates all mutable state that was previously scattered as module-level
    globals. This improves testability and makes the state lifecycle explicit.
    """

    def __init__(self) -> None:
        self.endpoints: dict[str, dict[str, Any]] = {}
        self.generation_logs: list[dict[str, str]] = []
        self._max_log_entries: int = 1000
        self._generator = MockGenerator(use_smart_fallback=True)

    @property
    def max_log_entries(self) -> int:
        return self._max_log_entries

    @max_log_entries.setter
    def max_log_entries(self, value: int) -> None:
        if value > 0:
            self._max_log_entries = value

    def add_log(self, level: str, message: str) -> None:
        self.generation_logs.append({
            "timestamp": datetime.now().isoformat(),
            "level": level,
            "message": message,
        })
        if len(self.generation_logs) > self._max_log_entries:
            self.generation_logs[:] = self.generation_logs[-self._max_log_entries:]

    def get_recent_logs(self, limit: int = 100) -> list[dict[str, str]]:
        return self.generation_logs[-limit:]

    def clear_logs(self) -> None:
        self.generation_logs.clear()

    def clear_endpoints(self) -> None:
        self.endpoints.clear()


app_state = AppState()


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

    @field_validator('method')
    @classmethod
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
        "llm": "not_configured"
    }
    llm_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if llm_key:
        services["llm"] = "configured"
    return services


def _add_log(level: str, message: str) -> None:
    app_state.add_log(level, message)


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
        "endpoints": list(app_state.endpoints.keys()),
        "total_generated": len([e for e in app_state.endpoints.values() if e.get("generated")]),
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

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="File is empty")

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

        app_state.clear_endpoints()

        result_endpoints = []
        for i, ep_data in enumerate(endpoints_data["endpoints"]):
            endpoint_id = f"ep_{i}"
            ep_data["id"] = endpoint_id

            app_state.endpoints[endpoint_id] = ep_data

            result_endpoints.append(EndpointInfo(
                id=endpoint_id,
                path=ep_data["resource_path"],
                method=ep_data["method"],
                status=ep_data.get("sample_responses", [{}])[0].get("status", 200),
                generated=False,
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

    if endpoint_id not in app_state.endpoints:
        raise HTTPException(status_code=404, detail=f"Endpoint not found: {endpoint_id}")

    endpoint = app_state.endpoints[endpoint_id]

    if endpoint.get("generated"):
        return {
            "success": True,
            "endpoint_id": endpoint_id,
            "cached": True,
            "message": "Endpoint already generated"
        }

    _add_log("info", f"Starting generation for {endpoint['method']} {endpoint['resource_path']}")

    result = None
    try:
        result = await asyncio.to_thread(app_state._generator.generate_endpoint, endpoint)

        if result.success:
            _add_log("success", f"Generated mock for {endpoint['method']} {endpoint['resource_path']}")
        else:
            _add_log("error", f"Generation failed: {result.error}")
    except Exception as e:
        _add_log("error", f"Generation error: {e}")

    succeeded = result is not None and result.success
    if succeeded:
        app_state.endpoints[endpoint_id]["generated"] = True
        app_state.endpoints[endpoint_id]["generated_at"] = datetime.now().isoformat()
        app_state.endpoints[endpoint_id]["generated_code"] = result.generated_code

    logger.info(f"Generated mock for endpoint: {endpoint_id} (success={succeeded})")

    return {
        "success": succeeded,
        "endpoint_id": endpoint_id,
        "cached": False,
        "logs": app_state.get_recent_logs(5),
        "generated_code": result.generated_code if succeeded else None,
        "error": result.error if result and not result.success else None,
    }


@app.get("/logs", tags=["System"])
async def get_logs(limit: int = Query(default=100, ge=1, le=1000)):
    return {"logs": app_state.get_recent_logs(limit)}


@app.delete("/logs", tags=["System"])
async def clear_logs():
    app_state.clear_logs()
    logger.info("Logs cleared")
    return {"success": True}


@app.get("/endpoints", tags=["Endpoints"])
async def list_endpoints(
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
):
    items = list(app_state.endpoints.values())
    total = len(items)
    return {
        "total": total,
        "offset": offset,
        "limit": limit,
        "endpoints": items[offset:offset + limit]
    }


@app.delete("/endpoints/{endpoint_id}", tags=["Endpoints"])
async def delete_endpoint(endpoint_id: str):
    if endpoint_id not in app_state.endpoints:
        raise HTTPException(status_code=404, detail="Endpoint not found")

    del app_state.endpoints[endpoint_id]

    logger.info(f"Deleted endpoint: {endpoint_id}")
    return {"success": True}


@app.post("/generate-all", tags=["Generation"])
async def generate_all_endpoints():
    pending = [
        (eid, ep) for eid, ep in app_state.endpoints.items()
        if not ep.get("generated")
    ]

    if not pending:
        return {
            "success": True,
            "generated_count": 0,
            "total_attempted": 0,
            "message": "All endpoints already generated"
        }

    _add_log("info", f"Starting batch generation for {len(pending)} endpoints")

    tasks = [
        asyncio.to_thread(app_state._generator.generate_endpoint, ep)
        for _, ep in pending
    ]

    results = await asyncio.gather(*tasks, return_exceptions=True)

    successful = 0
    for (endpoint_id, endpoint), result in zip(pending, results):
        if isinstance(result, Exception):
            _add_log("error", f"Generation error for {endpoint_id}: {result}")
            continue
        if result.success:
            successful += 1
            app_state.endpoints[endpoint_id]["generated"] = True
            app_state.endpoints[endpoint_id]["generated_at"] = datetime.now().isoformat()
            app_state.endpoints[endpoint_id]["generated_code"] = result.generated_code
            _add_log("success", f"Generated {endpoint['method']} {endpoint['resource_path']}")
        else:
            _add_log("error", f"Failed {endpoint['method']} {endpoint['resource_path']}: {result.error}")

    logger.info(f"Batch generation complete: {successful}/{len(pending)}")

    return {
        "success": True,
        "generated_count": successful,
        "total_attempted": len(pending)
    }


class StatsResponse(BaseModel):
    total_endpoints: int = Field(..., description="Total parsed endpoints")
    generated: int = Field(..., description="Number of generated endpoints")
    pending: int = Field(..., description="Number of endpoints awaiting generation")
    failures: int = Field(..., description="Number of failed generations")
    uptime: str = Field(..., description="Service uptime")


@app.get("/stats", response_model=StatsResponse, tags=["System"])
async def get_stats():
    """Return generation statistics and current state summary."""
    endpoints = app_state.endpoints
    generated = sum(1 for ep in endpoints.values() if ep.get("generated"))
    failures = sum(
        1 for log in app_state.get_recent_logs(1000)
        if log.get("level") == "error"
    )
    return StatsResponse(
        total_endpoints=len(endpoints),
        generated=generated,
        pending=len(endpoints) - generated,
        failures=failures,
        uptime=get_uptime(),
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
