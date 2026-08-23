"""Test-suite bootstrap.

Several modules under custom_components/noaa_tides import Home Assistant,
which isn't installed in this lightweight test environment. Helpers that
load HA-free modules directly from their file path (bypassing
noaa_tides/__init__.py) live in tests/_pure_import.py.
"""
