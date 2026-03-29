import sys
import asyncio
import httpx
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from generated_mocks.dynamic_api import app

async def test():
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),
        base_url='http://test'
    ) as client:
        r = await client.get('/health')
        print(f'✓ Health check: {r.status_code} - {r.json()}')
        
        r = await client.get('/mockclaw/info')
        print(f'✓ Info endpoint: {r.status_code} - {r.json()}')

asyncio.run(test())
