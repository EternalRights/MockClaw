"""
MockClaw Brain Service - FastAPI Backend
Provides REST API for the dashboard with production-ready features.
"""

import os
import sys
import json
import asyncio
import hashlib
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import logging

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from core.parser import HARParser  # noqa: E402

# Application metadata
APP_VERSION = "0.1.0"
START_TIME = time.time()

# Create FastAPI app
app = FastAPI(
    title="MockClaw Brain",
    description="AI-Powered Mock API Generator Backend",
    version=APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage (replace with database in production)
generated_endpoints: Dict[str, Dict[str, Any]] = {}
generation_logs: List[Dict[str, str]] = []
endpoint_cache: Dict[str, str] = {}  # Hash-based change detection


# ==================== Models ====================

class HealthResponse(BaseModel):
    """Health check response model."""
    status: str = Field(..., description="Service status")
    version: str = Field(..., description="Application version")
    uptime: str = Field(..., description="Service uptime")
    services: Dict[str, str] = Field(..., description="Service statuses")


class EndpointInfo(BaseModel):
    """Endpoint information model."""
    id: str = Field(..., description="Unique endpoint identifier")
    path: str = Field(..., description="API endpoint path")
    method: str = Field(..., description="HTTP method")
    status: int = Field(..., description="HTTP status code")
    generated: bool = Field(False, description="Whether mock is generated")
    hash: Optional[str] = Field(None, description="Content hash for change detection")
    
    @validator('method')
    def validate_method(cls, v):
        allowed = {'GET', 'POST', 'PUT', 'DELETE', 'PATCH', 'HEAD', 'OPTIONS'}
        if v.upper() not in allowed:
            raise ValueError(f"Invalid HTTP method: {v}")
        return v.upper()


class GenerateRequest(BaseModel):
    """Mock generation request model."""
    endpoint_id: str = Field(..., min_length=1, description="Endpoint to generate")


class ParseResponse(BaseModel):
    """HAR parse response model."""
    total_endpoints: int = Field(..., description="Number of endpoints found")
    endpoints: List[EndpointInfo] = Field(..., description="Parsed endpoints")
    processing_time_ms: int = Field(..., description="Processing duration")


class LogEntry(BaseModel):
    """Log entry model."""
    timestamp: str = Field(..., description="Log timestamp")
    level: str = Field(..., description="Log level")
    message: str = Field(..., description="Log message")


# ==================== Utility Functions ====================

def compute_endpoint_hash(endpoint_data: Dict[str, Any]) -> str:
    """
    Compute hash for endpoint data to detect changes.
    
    Args:
        endpoint_data: Dictionary containing endpoint information
        
    Returns:
        SHA256 hash string
    """
    content = json.dumps(endpoint_data, sort_keys=True)
    return hashlib.sha256(content.encode()).hexdigest()[:16]


def get_uptime() -> str:
    """
    Calculate service uptime.
    
    Returns:
        Human-readable uptime string
    """
    elapsed = time.time() - START_TIME
    hours, remainder = divmod(int(elapsed), 3600)
    minutes, seconds = divmod(remainder, 60)
    
    if hours > 0:
        return f"{hours}h {minutes}m"
    elif minutes > 0:
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"


def check_services() -> Dict[str, str]:
    """
    Check status of dependent services.
    
    Returns:
        Dictionary of service statuses
    """
    services = {
        "backend": "running",
        "docker": "unknown",
        "llm": "not_configured"
    }
    
    # Check Docker
    try:
        import docker
        client = docker.from_env(timeout=5)
        client.ping()
        services["docker"] = "running"
    except Exception:
        services["docker"] = "not_available"
    
    # Check LLM configuration
    llm_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if llm_key:
        services["llm"] = "configured"
    
    return services


# ==================== Error Handlers ====================

@app.exception_handler(json.JSONDecodeError)
async def json_decode_error(request: Request, exc: json.JSONDecodeError):
    """Handle JSON decode errors."""
    logger.error(f"JSON decode error: {exc}")
    return JSONResponse(
        status_code=400,
        content={"detail": "Invalid JSON in request body"}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle unexpected exceptions."""
    logger.exception(f"Unexpected error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error"}
    )


# ==================== Endpoints ====================

@app.get("/health", response_model=HealthResponse, tags=["System"])
async def health_check():
    """
    Comprehensive health check endpoint.
    
    Returns service status, version, uptime, and dependent service statuses.
    """
    return HealthResponse(
        status="ok",
        version=APP_VERSION,
        uptime=get_uptime(),
        services=check_services()
    )


@app.get("/mockclaw/info", tags=["System"])
async def mockclaw_info():
    """
    Get MockClaw metadata and statistics.
    """
    return {
        "generator": "MockClaw",
        "version": APP_VERSION,
        "endpoints": list(generated_endpoints.keys()),
        "total_generated": len([e for e in generated_endpoints.values() if e.get("generated")]),
        "uptime": get_uptime()
    }


@app.post("/parse", response_model=ParseResponse, tags=["Parsing"])
async def parse_har_file(file: UploadFile = File(...)):
    """
    Parse a HAR file and extract API endpoints.
    
    Args:
        file: HAR file upload
        
    Returns:
        Parsed endpoints with metadata
        
    Raises:
        HTTPException: If file is invalid or parsing fails
    """
    start_time = time.time()
    
    # Validate file type
    if not file.filename or not file.filename.endswith('.har'):
        raise HTTPException(status_code=400, detail="File must have .har extension")
    
    # Validate file size (max 50MB)
    content = await file.read()
    if len(content) > 50 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File too large (max 50MB)")
    
    try:
        json.loads(content.decode("utf-8"))  # validate JSON structure
    except (json.JSONDecodeError, UnicodeDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"Invalid file: {e}")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded")
    
    # Save to temp file for parser
    temp_path = Path("temp_upload.har")
    try:
        temp_path.write_bytes(content)
        
        # Parse HAR file
        parser = HARParser(str(temp_path))
        endpoints = parser.get_endpoints()
        
        # Build response
        result_endpoints = []
        for i, ep in enumerate(endpoints):
            endpoint_id = f"ep_{i}"
            endpoint_data = {
                "id": endpoint_id,
                "path": ep.resource_path,
                "method": ep.method,
                "status": ep.responses[0].status if ep.responses else 200,
                "sample_request": {
                    "url": ep.requests[0].url if ep.requests else "",
                    "body": ep.requests[0].body if ep.requests else None
                },
                "sample_response": {
                    "status": ep.responses[0].status if ep.responses else 200,
                    "body": ep.responses[0].body if ep.responses else None
                }
            }
            
            # Compute hash for change detection
            endpoint_data["hash"] = compute_endpoint_hash(endpoint_data)
            
            # Check if endpoint changed
            old_hash = endpoint_cache.get(endpoint_id)
            endpoint_data["changed"] = old_hash != endpoint_data["hash"]
            
            generated_endpoints[endpoint_id] = endpoint_data
            endpoint_cache[endpoint_id] = endpoint_data["hash"]
            
            result_endpoints.append(EndpointInfo(
                id=endpoint_id,
                path=ep.resource_path,
                method=ep.method,
                status=endpoint_data["status"],
                generated=False,
                hash=endpoint_data["hash"]
            ))
        
        processing_time = int((time.time() - start_time) * 1000)
        
        return ParseResponse(
            total_endpoints=len(endpoints),
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
    """
    Generate mock code for a specific endpoint.
    
    Args:
        request: Generation request with endpoint ID
        
    Returns:
        Generation result with logs
    """
    endpoint_id = request.endpoint_id
    
    if endpoint_id not in generated_endpoints:
        raise HTTPException(status_code=404, detail=f"Endpoint not found: {endpoint_id}")
    
    endpoint = generated_endpoints[endpoint_id]
    
    # Check if already generated and unchanged
    if endpoint.get("generated") and not endpoint.get("changed", False):
        return {
            "success": True,
            "endpoint_id": endpoint_id,
            "cached": True,
            "message": "Endpoint already generated, no changes detected"
        }
    
    # Generate logs
    logs = [
        {"timestamp": datetime.now().isoformat(), "level": "info", 
         "message": f"Starting generation for {endpoint['method']} {endpoint['path']}"},
        {"timestamp": datetime.now().isoformat(), "level": "thinking", 
         "message": "Analyzing HTTP request/response schema..."},
        {"timestamp": datetime.now().isoformat(), "level": "thinking", 
         "message": "Extracting field types and validation rules..."},
        {"timestamp": datetime.now().isoformat(), "level": "info", 
         "message": "Configuring Faker providers for realistic data..."},
        {"timestamp": datetime.now().isoformat(), "level": "success", 
         "message": f"Generated mock for {endpoint['method']} {endpoint['path']}"},
    ]
    
    # Simulate processing (replace with actual LLM call in production)
    await asyncio.sleep(1.5)
    
    # Mark as generated
    generated_endpoints[endpoint_id]["generated"] = True
    generated_endpoints[endpoint_id]["generated_at"] = datetime.now().isoformat()
    
    # Store logs
    generation_logs.extend(logs)
    
    logger.info(f"Generated mock for endpoint: {endpoint_id}")
    
    return {
        "success": True,
        "endpoint_id": endpoint_id,
        "cached": False,
        "logs": logs
    }


@app.get("/logs", tags=["System"])
async def get_logs(limit: int = 100):
    """
    Get generation logs.
    
    Args:
        limit: Maximum number of logs to return
        
    Returns:
        Recent log entries
    """
    return {"logs": generation_logs[-limit:]}


@app.delete("/logs", tags=["System"])
async def clear_logs():
    """Clear all generation logs."""
    global generation_logs
    generation_logs = []
    logger.info("Logs cleared")
    return {"success": True}


@app.get("/endpoints", tags=["Endpoints"])
async def list_endpoints():
    """List all parsed endpoints."""
    return {
        "total": len(generated_endpoints),
        "endpoints": list(generated_endpoints.values())
    }


@app.delete("/endpoints/{endpoint_id}", tags=["Endpoints"])
async def delete_endpoint(endpoint_id: str):
    """
    Delete a parsed endpoint.
    
    Args:
        endpoint_id: ID of endpoint to delete
    """
    if endpoint_id not in generated_endpoints:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    del generated_endpoints[endpoint_id]
    endpoint_cache.pop(endpoint_id, None)
    
    logger.info(f"Deleted endpoint: {endpoint_id}")
    return {"success": True}


@app.post("/generate-all", tags=["Generation"])
async def generate_all_endpoints():
    """Generate mocks for all endpoints in parallel."""
    results = []
    tasks = []
    
    for endpoint_id, endpoint in generated_endpoints.items():
        if not endpoint.get("generated") or endpoint.get("changed"):
            tasks.append(generate_mock(GenerateRequest(endpoint_id=endpoint_id)))
    
    if tasks:
        results = await asyncio.gather(*tasks, return_exceptions=True)
    
    successful = sum(1 for r in results if isinstance(r, dict) and r.get("success"))
    
    logger.info(f"Batch generation complete: {successful}/{len(tasks)}")
    
    return {
        "success": True,
        "generated_count": successful,
        "total_attempted": len(tasks)
    }


# ==================== Startup/Shutdown ====================

@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    logger.info(f"MockClaw Brain v{APP_VERSION} starting up...")
    
    # Check LLM configuration
    llm_key = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY")
    if not llm_key:
        logger.warning("LLM API key not configured. Mock generation will be limited.")
    else:
        logger.info("LLM API key configured")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown."""
    logger.info("MockClaw Brain shutting down...")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_level="info"
    )
