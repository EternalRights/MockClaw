import asyncio
import sys
import subprocess
import time
from pathlib import Path

sys.path.insert(0, 'src')

# Start server with visible output
print("Starting server with visible output...")
process = subprocess.Popen(
    [sys.executable, "-m", "uvicorn", "generated_mocks.dynamic_api:app", "--host", "0.0.0.0", "--port", "8000", "--log-level", "debug"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == 'win32' else 0
)

time.sleep(3)

# Test with requests
try:
    import requests
    
    print("\n=== Test 1: Health Check ===")
    r = requests.get("http://localhost:8000/health", timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
    
    print("\n=== Test 2: Path Traversal ===")
    r = requests.get("http://localhost:8000/../../etc/passwd", timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
    
    print("\n=== Test 3: POST with garbage ===")
    r = requests.post("http://localhost:8000/health", json={"data": None}, timeout=5)
    print(f"Status: {r.status_code}")
    print(f"Response: {r.text}")
    
except Exception as e:
    print(f"Error: {e}")

finally:
    print("\n=== Server Logs ===")
    process.send_signal(8)  # SIGBREAK on Windows
    stdout, _ = process.communicate(timeout=5)
    print(stdout[-5000:] if len(stdout) > 5000 else stdout)
