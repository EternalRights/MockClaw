"""
MockClaw Brain Service - FastAPI Backend
Provides REST API for the dashboard to interact with the generator.
"""

import os
import sys
import json
import asyncio
from pathlib import Path
from typing import Optional
from datetime import datetime

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from core.parser import HARParser
from core.generator import MockGenerator

# Create FastAPI app
app = FastAPI(
    title="MockClaw Brain",
    description="AI-Powered Mock API Generator Backend",
    version="0.1.0"
)

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store for generated endpoints
generated_endpoints = {}
generation_logs = []


class EndpointInfo(BaseModel):
    id: str
    path: str
    method: str
    status: int
    generated: bool = False


class GenerateRequest(BaseModel):
    endpoint_id: str


class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "OK", "service": "MockClaw Brain"}


@app.get("/mockclaw/info")
async def mockclaw_info():
    """Get MockClaw metadata."""
    return {
        "generator": "MockClaw",
        "version": "0.1.0",
        "endpoints": list(generated_endpoints.keys()),
        "total_generated": len([e for e in generated_endpoints.values() if e.get("generated")])
    }


@app.post("/parse")
async def parse_har_file(file: UploadFile = File(...)):
    """Parse a HAR file and extract endpoints."""
    if not file.filename.endswith('.har'):
        raise HTTPException(status_code=400, detail="File must be a .har file")
    
    try:
        # Read file content
        content = await file.read()
        har_data = json.loads(content.decode('utf-8'))
        
        # Save to temp file
        temp_path = Path("temp_upload.har")
        temp_path.write_bytes(content)
        
        # Parse
        parser = HARParser(str(temp_path))
        endpoints = parser.get_endpoints()
        
        # Format response
        result = {
            "total_endpoints": len(endpoints),
            "endpoints": [
                {
                    "id": f"ep_{i}",
                    "path": ep.resource_path,
                    "method": ep.method,
                    "status": ep.responses[0].status if ep.responses else 200,
                    "generated": False,
                    "sample_request": {
                        "url": ep.requests[0].url if ep.requests else "",
                        "body": ep.requests[0].body if ep.requests else None
                    },
                    "sample_response": {
                        "status": ep.responses[0].status if ep.responses else 200,
                        "body": ep.responses[0].body if ep.responses else None
                    }
                }
                for i, ep in enumerate(endpoints)
            ]
        }
        
        # Store endpoints
        for ep in result["endpoints"]:
            generated_endpoints[ep["id"]] = ep
        
        # Cleanup
        temp_path.unlink(missing_ok=True)
        
        return result
        
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid HAR file format")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/generate")
async def generate_mock(request: GenerateRequest):
    """Generate mock code for a specific endpoint."""
    endpoint_id = request.endpoint_id
    
    if endpoint_id not in generated_endpoints:
        raise HTTPException(status_code=404, detail="Endpoint not found")
    
    endpoint = generated_endpoints[endpoint_id]
    
    # Add log entries
    logs = [
        {"timestamp": datetime.now().isoformat(), "level": "info", "message": f"Starting generation for {endpoint['method']} {endpoint['path']}"},
        {"timestamp": datetime.now().isoformat(), "level": "thinking", "message": "Analyzing HTTP request/response schema..."},
        {"timestamp": datetime.now().isoformat(), "level": "thinking", "message": "Extracting field types and validation rules..."},
        {"timestamp": datetime.now().isoformat(), "level": "info", "message": "Configuring Faker providers for realistic data..."},
        {"timestamp": datetime.now().isoformat(), "level": "success", "message": f"Generated mock for {endpoint['method']} {endpoint['path']}"},
    ]
    
    # Simulate processing time
    await asyncio.sleep(1.5)
    
    # Mark as generated
    generated_endpoints[endpoint_id]["generated"] = True
    
    # Store logs
    generation_logs.extend(logs)
    
    return {
        "success": True,
        "endpoint_id": endpoint_id,
        "logs": logs
    }


@app.get("/logs")
async def get_logs():
    """Get generation logs."""
    return {"logs": generation_logs[-100:]}  # Last 100 logs


@app.delete("/logs")
async def clear_logs():
    """Clear generation logs."""
    global generation_logs
    generation_logs = []
    return {"success": True}


@app.get("/endpoints")
async def list_endpoints():
    """List all parsed endpoints."""
    return {
        "total": len(generated_endpoints),
        "endpoints": list(generated_endpoints.values())
    }


@app.post("/generate-all")
async def generate_all_endpoints():
    """Generate mocks for all endpoints."""
    results = []
    
    for endpoint_id, endpoint in generated_endpoints.items():
        if not endpoint.get("generated"):
            result = await generate_mock(GenerateRequest(endpoint_id=endpoint_id))
            results.append(result)
    
    return {
        "success": True,
        "generated_count": len(results)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
