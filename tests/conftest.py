"""Test-suite bootstrap.

Makes the repo root importable as `custom_components` (needed by tests that
import the real Home Assistant-dependent modules, e.g. test_pressure_units.py
-- see requirements-test.txt for the `homeassistant` pip package that makes
those imports work standalone).

Some modules (e.g. tide_selection.py) have no Home Assistant dependency and
are loaded directly from their file path instead, bypassing
noaa_tides/__init__.py; see tests/_pure_import.py for that helper.
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
