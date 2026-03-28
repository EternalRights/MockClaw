"""
MockClaw Main CLI
Watches input_har folder and auto-generates mock APIs.
"""

import os
import sys
import time
import json
import subprocess
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8')

from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

from core.parser import HARParser
from core.generator import MockGenerator


class HARFileHandler(FileSystemEventHandler):
    """Handles new HAR file detection."""
    
    def __init__(self, generator: MockGenerator, input_dir: str, output_dir: str):
        self.generator = generator
        self.input_dir = Path(input_dir)
        self.output_dir = Path(output_dir)
        self.processing = set()
        
    def on_created(self, event):
        """Handle new file creation."""
        if event.is_directory:
            return
        
        file_path = Path(event.src_path)
        if file_path.suffix == '.har' and file_path not in self.processing:
            self._process_har_file(file_path)
    
    def _process_har_file(self, har_path: Path):
        """Process a HAR file and generate mocks."""
        print(f"\n📥 New HAR file detected: {har_path.name}")
        self.processing.add(har_path)
        
        try:
            # Step 1: Parse HAR
            print("🔍 Parsing traffic...")
            parser = HARParser(str(har_path))
            endpoints_data = parser.export_as_dict()
            print(f"   Found {endpoints_data['total_endpoints']} API endpoints")
            
            # Step 2: Generate mocks
            print("🤖 Generating mock code...")
            results = self.generator.generate_all(
                endpoints_data['endpoints'],
                str(self.output_dir)
            )
            
            success_count = sum(1 for r in results if r.success)
            print(f"   Generated {success_count}/{len(results)} endpoints successfully")
            
            # Step 3: Show generated file
            generated_file = self.output_dir / "dynamic_api.py"
            if generated_file.exists():
                print(f"   💾 Saved to: {generated_file}")
                
            # Step 4: Offer to restart mock server
            print("\n🚀 To deploy, run:")
            print(f"   docker-compose -f {Path.cwd() / 'docker-compose.yml'} up -d mock-server")
            
        except Exception as e:
            print(f"❌ Error processing {har_path.name}: {e}")
        finally:
            self.processing.discard(har_path)


def create_test_har_file(output_path: str = "test_data/sample_login.har"):
    """Create a sample HAR file for testing."""
    har_content = {
        "log": {
            "version": "1.2",
            "creator": {
                "name": "MockClaw Test Generator",
                "version": "0.1.0"
            },
            "entries": [
                {
                    "startedDateTime": "2026-03-28T10:00:00.000Z",
                    "time": 150,
                    "request": {
                        "method": "POST",
                        "url": "https://api.example.com/api/login",
                        "httpVersion": "HTTP/1.1",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"},
                            {"name": "Accept", "value": "application/json"}
                        ],
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
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"}
                        ],
                        "content": {
                            "mimeType": "application/json",
                            "text": '{"token":"eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9","user":{"id":1,"username":"testuser","email":"test@example.com"}}'
                        },
                        "redirectURL": "",
                        "headersSize": -1,
                        "bodySize": 180
                    },
                    "cache": {},
                    "timings": {
                        "send": 0,
                        "wait": 100,
                        "receive": 10
                    }
                },
                {
                    "startedDateTime": "2026-03-28T10:00:01.000Z",
                    "time": 80,
                    "request": {
                        "method": "GET",
                        "url": "https://api.example.com/api/users/123",
                        "httpVersion": "HTTP/1.1",
                        "headers": [
                            {"name": "Authorization", "value": "Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}
                        ],
                        "queryString": [
                            {"name": "include", "value": "profile"},
                            {"name": "status", "value": "active"}
                        ],
                        "postData": None,
                        "headersSize": -1,
                        "bodySize": 0
                    },
                    "response": {
                        "status": 200,
                        "statusText": "OK",
                        "httpVersion": "HTTP/1.1",
                        "headers": [
                            {"name": "Content-Type", "value": "application/json"}
                        ],
                        "content": {
                            "mimeType": "application/json",
                            "text": '{"id":123,"name":"John Doe","email":"john@example.com","profile":{"bio":"Software Engineer","avatar":"https://example.com/avatar.jpg"}}'
                        },
                        "redirectURL": "",
                        "headersSize": -1,
                        "bodySize": 200
                    },
                    "cache": {},
                    "timings": {
                        "send": 0,
                        "wait": 60,
                        "receive": 10
                    }
                }
            ]
        }
    }
    
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(har_content, indent=2), encoding='utf-8')
    print(f"✅ Created test HAR file: {output_path}")
    return output_path


def main():
    """Main CLI entry point."""
    print("""
+==============================================================+
|                    MockClaw v0.1.0                          |
|          AI-Powered Mock API Generator from Traffic          |
+==============================================================+
    """)
    
    # Setup directories
    base_dir = Path(__file__).parent.parent
    input_dir = base_dir / "input_har"
    output_dir = base_dir / "generated_mocks"
    test_data_dir = base_dir / "test_data"
    
    input_dir.mkdir(exist_ok=True)
    output_dir.mkdir(exist_ok=True)
    test_data_dir.mkdir(exist_ok=True)
    
    # Initialize generator
    generator = MockGenerator()
    
    # Check for --generate-test flag
    if '--generate-test' in sys.argv or '-t' in sys.argv:
        print("🎯 Generating test HAR file...")
        create_test_har_file(str(test_data_dir / "sample_login.har"))
        
        print("\n🔄 Running test generation...")
        har_path = test_data_dir / "sample_login.har"
        parser = HARParser(str(har_path))
        endpoints_data = parser.export_as_dict()
        results = generator.generate_all(endpoints_data['endpoints'], str(output_dir))
        
        success = all(r.success for r in results)
        print(f"\n{'✅ Test generation PASSED' if success else '❌ Test generation FAILED'}")
        
        if (output_dir / "dynamic_api.py").exists():
            print(f"   Generated file: {output_dir / 'dynamic_api.py'}")
        
        return 0 if success else 1
    
    # Check for direct HAR file processing
    if len(sys.argv) > 1 and sys.argv[1].endswith('.har'):
        har_path = Path(sys.argv[1])
        print(f"📂 Processing: {har_path}")
        
        parser = HARParser(str(har_path))
        endpoints_data = parser.export_as_dict()
        print(f"📊 Found {endpoints_data['total_endpoints']} endpoints")
        
        results = generator.generate_all(endpoints_data['endpoints'], str(output_dir))
        
        for r in results:
            print(f"  {'✅' if r.success else '❌'} {r.endpoint_path}")
        
        print(f"\n💾 Output: {output_dir / 'dynamic_api.py'}")
        return 0
    
    # Watch mode
    print(f"📁 Watching: {input_dir}")
    print("   Drop a .har file to generate mocks")
    print("   Press Ctrl+C to stop\n")
    
    event_handler = HARFileHandler(generator, str(input_dir), str(output_dir))
    observer = Observer()
    observer.schedule(event_handler, str(input_dir), recursive=False)
    observer.start()
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n👋 Shutting down...")
        observer.stop()
    observer.join()
    
    return 0


if __name__ == "__main__":
    sys.exit(main())
