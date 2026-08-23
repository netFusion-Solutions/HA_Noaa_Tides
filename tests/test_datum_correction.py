"""Tests for the fork-only, opt-in datum-correction feature.

Covers the verification checklist from the design brief:
  - the corrected residual (observed - corrected prediction) centers near
    zero over a 7-day window, unlike the raw astronomical residual;
  - the offset-lookup failure paths never take tide_predictions
    unavailable -- they fall back to the cached offset (or 0.0).

compute_datum_offset() (custom_components/noaa_tides/datum_offset.py) has
no Home Assistant dependency and is exercised directly against live NOAA
data. The coordinator-level tests build a NoaaTidesDataUpdateCoordinator
without a running Home Assistant Core (object.__new__, bypassing
DataUpdateCoordinator.__init__) since _async_refresh_datum_offset and
_apply_datum_correction only touch datum-specific attributes and the
injected api_client, not the Home Assistant-provided ones.
"""

from __future__ import annotations

import asyncio
import json
import urllib.error
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta

import pytest

from custom_components.noaa_tides.coordinator import NoaaTidesDataUpdateCoordinator
from custom_components.noaa_tides.datum_offset import (
    DatumLookupError,
    compute_datum_offset,
)

STATION = "8531680"  # Sandy Hook, NJ -- Rob's production station


def _noaa_get(**params) -> dict:
    params.setdefault("station", STATION)
    params.setdefault("format", "json")
    params.setdefault("application", "noaa_tides_tests")
    params.setdefault("time_zone", "lst_ldt")
    params.setdefault("units", "english")
    query = "&".join(f"{k}={v}" for k, v in params.items())
    url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?" + query
    try:
        with urllib.request.urlopen(url, timeout=25) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError) as err:
        pytest.skip(f"NOAA API unreachable: {err}")


def _fetch_datums(station: str = STATION) -> dict:
    url = f"https://api.tidesandcurrents.noaa.gov/mdapi/prod/webapi/stations/{station}/datums.json"
    try:
        with urllib.request.urlopen(url, timeout=25) as resp:
            return json.load(resp)
    except (urllib.error.URLError, TimeoutError) as err:
        pytest.skip(f"NOAA mdapi unreachable: {err}")


def _fetch_monthly_mean(unit_system: str, station: str = STATION) -> list[dict]:
    units = "metric" if unit_system == "Metric" else "english"
    end = datetime.now()
    begin = end - timedelta(days=200)
    data = _noaa_get(
        product="monthly_mean",
        datum="STND",
        time_zone="lst",
        units=units,
        begin_date=begin.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
        station=station,
    )
    return data.get("data", [])


# ---------------------------------------------------------------------------
# compute_datum_offset() against live data
# ---------------------------------------------------------------------------


def test_compute_datum_offset_is_plausible_and_positive() -> None:
    """Sandy Hook runs persistently above prediction (see PROMPT.md); the
    seasonal climatology table there ranges +0.23 to +0.87 ft, and the
    live spot/7-day/climatology cross-checks all land in a similar band.
    """
    datums = _fetch_datums()
    rows = _fetch_monthly_mean("Imperial")
    if not rows:
        pytest.skip("No monthly_mean data available")

    result = compute_datum_offset(datums, rows, "Imperial")

    assert 0.1 <= result["offset"] <= 1.5
    assert result["epoch"] == "1983-2001"
    assert result["source"].startswith("monthly_mean ")


def test_compute_datum_offset_metric_matches_imperial() -> None:
    """Converting datums.json's feet to meters should agree with fetching
    monthly_mean directly in metric units, within rounding.
    """
    datums = _fetch_datums()
    imperial_rows = _fetch_monthly_mean("Imperial")
    metric_rows = _fetch_monthly_mean("Metric")
    if not imperial_rows or not metric_rows:
        pytest.skip("No monthly_mean data available")

    imperial = compute_datum_offset(datums, imperial_rows, "Imperial")
    metric = compute_datum_offset(datums, metric_rows, "Metric")

    assert metric["offset"] == pytest.approx(imperial["offset"] / 3.28084, abs=0.02)


def test_compute_datum_offset_raises_when_msl_datum_missing() -> None:
    datums_without_msl = {"epoch": "1983-2001", "units": "feet", "datums": [
        {"name": "MLLW", "value": 2.51}
    ]}
    with pytest.raises(DatumLookupError):
        compute_datum_offset(datums_without_msl, [{"MSL": "5.0", "year": "2026", "month": "1"}], "Imperial")


def test_compute_datum_offset_raises_when_monthly_mean_empty() -> None:
    datums = {"epoch": "1983-2001", "units": "feet", "datums": [{"name": "MSL", "value": 5.09}]}
    with pytest.raises(DatumLookupError):
        compute_datum_offset(datums, [], "Imperial")


# ---------------------------------------------------------------------------
# Verification #2: corrected residual centers near zero over a 7-day window
# ---------------------------------------------------------------------------


def test_corrected_residual_centers_near_zero_over_7_days() -> None:
    """Ported from research/residual_trend.py, extended to apply the datum
    offset. The raw astronomical residual runs persistently positive
    (measured +0.64 ft over 7 days in the design brief); correcting by the
    live offset should pull the mean residual close to zero.
    """
    end = datetime.now()
    begin = end - timedelta(days=7)
    predictions = _noaa_get(
        product="predictions",
        datum="MLLW",
        interval="6",
        begin_date=begin.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    ).get("predictions", [])
    observed = _noaa_get(
        product="water_level",
        datum="MLLW",
        begin_date=begin.strftime("%Y%m%d"),
        end_date=end.strftime("%Y%m%d"),
    ).get("data", [])
    if not predictions or not observed:
        pytest.skip("No predictions/observations available for the residual window")

    datums = _fetch_datums()
    monthly_rows = _fetch_monthly_mean("Imperial")
    if not monthly_rows:
        pytest.skip("No monthly_mean data available")
    offset = compute_datum_offset(datums, monthly_rows, "Imperial")["offset"]

    pred_by_time = {p["t"]: float(p["v"]) for p in predictions}

    raw_residuals = []
    corrected_residuals = []
    for row in observed:
        t, v = row["t"], row.get("v")
        if t not in pred_by_time or v in (None, ""):
            continue
        observed_level = float(v)
        predicted = pred_by_time[t]
        raw_residuals.append(observed_level - predicted)
        corrected_residuals.append(observed_level - (predicted + offset))

    if not raw_residuals:
        pytest.skip("No overlapping prediction/observation timestamps")

    raw_mean = sum(raw_residuals) / len(raw_residuals)
    corrected_mean = sum(corrected_residuals) / len(corrected_residuals)

    # The correction should meaningfully reduce the bias, and the result
    # should sit close to zero rather than merely "less positive".
    assert abs(corrected_mean) < abs(raw_mean)
    assert abs(corrected_mean) < 0.4, (
        f"corrected 7-day mean residual {corrected_mean:+.3f} ft did not "
        f"center near zero (raw was {raw_mean:+.3f} ft, offset {offset:+.2f} ft)"
    )


# ---------------------------------------------------------------------------
# Verification #4: offset-lookup failures never take the entity unavailable
# ---------------------------------------------------------------------------


class _FailingApiClient:
    async def async_get_datum_offset(self):
        raise RuntimeError("simulated NOAA outage")


class _SucceedingApiClient:
    def __init__(self, offset: float, source: str, epoch: str) -> None:
        self._result = {"offset": offset, "source": source, "epoch": epoch}

    async def async_get_datum_offset(self):
        return self._result


def _bare_coordinator(api_client, datum_correction_enabled: bool = True):
    """Build a coordinator without a running Home Assistant Core.

    _async_refresh_datum_offset and _apply_datum_correction only touch
    datum-specific state and the injected api_client, so bypassing
    DataUpdateCoordinator.__init__ (which needs a real `hass`) is safe here.
    """
    coordinator = object.__new__(NoaaTidesDataUpdateCoordinator)
    coordinator.station_id = STATION
    coordinator.datum_correction_enabled = datum_correction_enabled
    coordinator._datum_offset = 0.0
    coordinator._datum_offset_source = None
    coordinator._datum_epoch = None
    coordinator._datum_offset_fetched_month = None
    coordinator.api_client = api_client
    return coordinator


def test_refresh_survives_lookup_failure_with_no_prior_cache() -> None:
    coordinator = _bare_coordinator(_FailingApiClient())

    asyncio.run(coordinator._async_refresh_datum_offset())  # must not raise

    assert coordinator._datum_offset == 0.0
    assert coordinator._datum_offset_fetched_month is None  # will retry next cycle


def test_refresh_keeps_cached_offset_after_later_failure() -> None:
    coordinator = _bare_coordinator(
        _SucceedingApiClient(0.82, "monthly_mean 2026-07", "1983-2001")
    )
    asyncio.run(coordinator._async_refresh_datum_offset())
    assert coordinator._datum_offset == 0.82

    # A new month rolls around and the lookup starts failing.
    coordinator._datum_offset_fetched_month = (1999, 1)
    coordinator.api_client = _FailingApiClient()
    asyncio.run(coordinator._async_refresh_datum_offset())

    assert coordinator._datum_offset == 0.82
    assert coordinator._datum_offset_source == "monthly_mean 2026-07"


def test_refresh_skips_lookup_entirely_when_disabled() -> None:
    coordinator = _bare_coordinator(_FailingApiClient(), datum_correction_enabled=False)
    asyncio.run(coordinator._async_refresh_datum_offset())  # must not raise or call the client
    assert coordinator._datum_offset == 0.0


def test_apply_datum_correction_preserves_raw_and_adds_metadata() -> None:
    coordinator = _bare_coordinator(_SucceedingApiClient(0.5, "monthly_mean 2026-07", "1983-2001"))
    coordinator._datum_offset = 0.5
    coordinator._datum_offset_source = "monthly_mean 2026-07"
    coordinator._datum_epoch = "1983-2001"

    data = {
        "tide_predictions": {
            "state": "High tide at 3:00 PM",
            "attributes": {
                "next_tide_level": 4.0,
                "last_tide_level": 1.0,
                "following_tide_level": 3.5,
            },
        }
    }
    coordinator._apply_datum_correction(data)

    attrs = data["tide_predictions"]["attributes"]
    assert attrs["raw_next_tide_level"] == 4.0
    assert attrs["next_tide_level"] == 4.5
    assert attrs["raw_last_tide_level"] == 1.0
    assert attrs["last_tide_level"] == 1.5
    assert attrs["raw_following_tide_level"] == 3.5
    assert attrs["following_tide_level"] == 4.0
    assert attrs["datum_offset"] == 0.5
    assert attrs["datum_offset_source"] == "monthly_mean 2026-07"
    assert attrs["datum_epoch"] == "1983-2001"


def test_apply_datum_correction_handles_missing_following_tide() -> None:
    coordinator = _bare_coordinator(_SucceedingApiClient(0.5, "s", "e"))
    coordinator._datum_offset = 0.5

    data = {
        "tide_predictions": {
            "state": "x",
            "attributes": {"next_tide_level": 4.0, "last_tide_level": 1.0},
        }
    }
    coordinator._apply_datum_correction(data)  # must not KeyError

    attrs = data["tide_predictions"]["attributes"]
    assert "raw_following_tide_level" not in attrs
    assert attrs["next_tide_level"] == 4.5


def test_apply_datum_correction_is_a_noop_without_tide_predictions() -> None:
    coordinator = _bare_coordinator(_SucceedingApiClient(0.5, "s", "e"))
    data = {}

    coordinator._apply_datum_correction(data)  # must not raise

    assert data == {}
