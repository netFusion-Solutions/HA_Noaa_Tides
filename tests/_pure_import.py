"""Load an HA-free module from custom_components/noaa_tides by file path.

Importing it the normal way (``custom_components.noaa_tides.tide_selection``)
would execute ``noaa_tides/__init__.py``, which imports Home Assistant.
These modules have no such dependency, so load them directly instead.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

_PACKAGE_DIR = Path(__file__).resolve().parents[1] / "custom_components" / "noaa_tides"


def load(module_name: str) -> ModuleType:
    """Import ``custom_components/noaa_tides/{module_name}.py`` in isolation."""
    path = _PACKAGE_DIR / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module
