import json
from pathlib import Path
import sys
sys.path.insert(0, 'src')

from core.parser import HARParser
from core.generator import MockGenerator

har = {
    "log": {
        "version": "1.2",
        "creator": {"name": "Test", "version": "0.1.0"},
        "entries": [{
            "startedDateTime": "2026-03-28T10:00:00.000Z",
            "time": 150,
            "request": {
                "method": "POST",
                "url": "https://api.example.com/api/login",
                "httpVersion": "HTTP/1.1",
                "headers": [{"name": "Content-Type", "value": "application/json"}],
                "queryString": [],
                "postData": {
                    "mimeType": "application/json",
                    "text": '{"username":"testuser","password":"secret123"}'
                },
                "headersSize": -1,
                "bodySize": 45
            },
            "response": {
                "status": 200,
                "statusText": "OK",
                "httpVersion": "HTTP/1.1",
                "headers": [{"name": "Content-Type", "value": "application/json"}],
                "content": {
                    "mimeType": "application/json",
                    "text": '{"token":"mock_jwt_token","user":{"id":1,"username":"testuser"}}'
                },
                "redirectURL": "",
                "headersSize": -1,
                "bodySize": 150
            },
            "cache": {},
            "timings": {"send": 0, "wait": 100, "receive": 10}
        }]
    }
}

Path('test_data/chaos_test.har').write_text(json.dumps(har))
parser = HARParser('test_data/chaos_test.har')
gen = MockGenerator()
results = gen.generate_all(parser.export_as_dict()['endpoints'], 'generated_mocks')
print(f'Generated {len(results)} endpoints')
