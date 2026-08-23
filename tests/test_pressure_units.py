"""Regression test for Bug 2: barometric pressure mislabeled as inHg.

NOAA's CO-OPS air_pressure product always returns millibars, regardless of
the requested `units` parameter. The imperial sensor description used to be
labelled inHg, so Home Assistant applied an hPa->inHg display conversion to
an already-mb value, inflating the displayed pressure by ~33.86x (e.g. Sandy
Hook's 1018.7 mb showing as ~34500 "hPa").

Two things are checked:
- the sensor description reports native hPa in both unit systems (the
  actual fix, exercised through the real utils.get_unit_for_sensor code
  path used by sensor.py), and
- live NOAA data confirms the root cause: units=english and units=metric
  return the same plausible millibar value, not different units.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request

import pytest

from custom_components.noaa_tides import const, utils
from custom_components.noaa_tides.sensors.noaa_sensors import NOAA_SENSOR_TYPES

STATION = "8531680"  # Sandy Hook, NJ -- Rob's production station

# Real atmospheric pressure at sea level; generous margin around the
# ~950-1050 mb range actually seen in practice.
PLAUSIBLE_HPA_RANGE = (900.0, 1100.0)


@pytest.mark.parametrize("unit_system", [const.UNIT_METRIC, const.UNIT_IMPERIAL])
def test_air_pressure_native_unit_is_hpa_in_both_systems(unit_system: str) -> None:
    """The fix: air_pressure must report hPa regardless of unit_system."""
    description = NOAA_SENSOR_TYPES["air_pressure"]
    unit = utils.get_unit_for_sensor(
        description, unit_system, const.STATION_TYPE_NOAA, "air_pressure"
    )
    assert unit == "hPa"


def _fetch_air_pressure(units: str) -> float:
    params = (
        f"station={STATION}&product=air_pressure&time_zone=lst_ldt"
        f"&units={units}&format=json&date=latest&application=noaa_tides_tests"
    )
    url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?" + params
    try:
        with urllib.request.urlopen(url, timeout=25) as resp:
            payload = json.load(resp)
    except (urllib.error.URLError, TimeoutError) as err:
        pytest.skip(f"NOAA API unreachable: {err}")
    if "error" in payload or not payload.get("data"):
        pytest.skip(f"NOAA API returned no air_pressure data: {payload}")
    return float(payload["data"][0]["v"])


@pytest.mark.parametrize("units", ["english", "metric"])
def test_noaa_air_pressure_is_always_millibars(units: str) -> None:
    """Root cause: units=english returns mb, not inHg (proof for the PR)."""
    value = _fetch_air_pressure(units)
    assert PLAUSIBLE_HPA_RANGE[0] <= value <= PLAUSIBLE_HPA_RANGE[1], (
        f"units={units} returned {value}, outside plausible sea-level "
        f"pressure range {PLAUSIBLE_HPA_RANGE} -- if NOAA started returning "
        f"true inHg for units=english this value would be ~30, not ~1000"
    )
