"""
MockClaw Version Utility
Single source of truth for package version extraction.
"""

from __future__ import annotations

import re
from pathlib import Path


def get_version(package: str = "mockclaw", default: str = "0.2.0") -> str:
    try:
        from importlib.metadata import version as _pkg_version
        return _pkg_version(package)
    except Exception:
        _init = Path(__file__).parent / "__init__.py"
        if _init.exists():
            _m = re.search(
                r'^__version__\s*=\s*["\']([^"\']+)',
                _init.read_text(encoding="utf-8"),
                re.MULTILINE,
            )
            if _m:
                return _m.group(1)
        return default
