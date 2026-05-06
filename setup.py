"""
MockClaw Setup
Install with: pip install -e .
"""

from setuptools import setup, find_packages
from pathlib import Path
import re

readme_path = Path(__file__).parent / "README.md"
long_description = readme_path.read_text(encoding="utf-8") if readme_path.exists() else ""

requirements_path = Path(__file__).parent / "src" / "requirements.txt"
requirements = [
    line.strip()
    for line in requirements_path.read_text(encoding="utf-8").splitlines()
    if line.strip() and not line.startswith("#")
]

init_path = Path(__file__).parent / "src" / "__init__.py"
_version_match = re.search(r'^__version__\s*=\s*["\']([^"\']+)', init_path.read_text(encoding="utf-8"), re.MULTILINE)
_version = _version_match.group(1) if _version_match else "0.2.0"

setup(
    name="mockclaw",
    version=_version,
    author="MockClaw Team",
    author_email="mockclaw@example.com",
    description="Generate mock APIs from HAR files with chaos engineering",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/EternalRights/MockClaw",
    packages=find_packages(where="src"),
    package_dir={"": "src"},
    classifiers=[
        "Development Status :: 4 - Beta",
        "Intended Audience :: Developers",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
        "Programming Language :: Python :: 3",
        "Programming Language :: Python :: 3.11",
        "Programming Language :: Python :: 3.12",
        "Topic :: Software Development :: Testing",
        "Topic :: Software Development :: Testing :: Mocking",
    ],
    python_requires=">=3.11",
    install_requires=requirements,
    entry_points={
        "console_scripts": [
            "mockclaw=cli:app",
        ],
    },
    include_package_data=True,
    extras_require={
        "dev": [
            "pytest>=8.0.0",
            "ruff>=0.1.0",
            "mypy>=1.8.0",
        ],
        "llm": [
            "openai>=1.10.0",
        ],
        "perf": [
            "orjson>=3.9.0",
        ],
        "docker": [
            "docker>=7.0.0",
        ],
        "test": [
            "httpx>=0.26.0",
        ],
    },
)
