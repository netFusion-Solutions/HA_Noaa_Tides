"""Regression test for Bug 1: tide predictions dying between midnight and
the day's first tide.

Ported from research/window_repro.py and research/window_compare.py. Hits
the live NOAA CO-OPS API (no key required) and replays the tide-selection
logic at 15-minute resolution across a full day for several stations,
asserting the fixed window (begin_date=yesterday, range=72h) never fails to
find a last/next tide.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from datetime import datetime, timedelta

import pytest

from _pure_import import load

tide_selection = load("tide_selection")
select_tide_window = tide_selection.select_tide_window

# Must match data_constants.MAX_PREDICTION_HOURS.
FETCH_RANGE_HOURS = 72

STATIONS = [
    "8531680",  # Sandy Hook, NJ -- Rob's production station
    "9414290",  # San Francisco, CA -- large mixed-semidiurnal range
    "8452660",  # Newport, RI -- small range
]


def _fetch_predictions(station: str, begin_date: str, range_hours: int) -> list[dict]:
    params = (
        f"station={station}&product=predictions&datum=MLLW&time_zone=lst_ldt"
        f"&units=english&format=json&interval=hilo&begin_date={begin_date}"
        f"&range={range_hours}&application=noaa_tides_tests"
    )
    url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter?" + params
    try:
        with urllib.request.urlopen(url, timeout=25) as resp:
            payload = json.load(resp)
    except (urllib.error.URLError, TimeoutError) as err:
        pytest.skip(f"NOAA API unreachable: {err}")
    if "error" in payload:
        pytest.skip(f"NOAA API error for station {station}: {payload['error']}")
    return payload.get("predictions", [])


def _formatted(predictions: list[dict]) -> list[dict]:
    return [
        {
            "time": datetime.strptime(p["t"], "%Y-%m-%d %H:%M"),
            "type": p["type"],
            "level": float(p["v"]),
        }
        for p in predictions
    ]


@pytest.mark.parametrize("station", STATIONS)
def test_fixed_window_never_loses_last_and_next_tide(station: str) -> None:
    """Replay selection every 15 min across a day; last/next must always resolve."""
    begin_date = (datetime.now() - timedelta(days=1)).strftime("%Y%m%d")
    raw = _fetch_predictions(station, begin_date, FETCH_RANGE_HOURS)
    if not raw:
        pytest.skip(f"No predictions returned for station {station}")
    predictions = _formatted(raw)

    base = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    samples = [base + timedelta(minutes=15 * i) for i in range(96)]

    failures = [
        now
        for now in samples
        if not all(select_tide_window(predictions, now)[:2])
    ]

    assert not failures, (
        f"station {station}: {len(failures)} of {len(samples)} samples had no "
        f"last/next tide, e.g. {failures[0]:%H:%M}-{failures[-1]:%H:%M}"
    )


def test_current_upstream_window_fails_overnight() -> None:
    """Documents the bug being fixed: begin=today/range=48 loses the tide
    between midnight and the day's first tide (Sandy Hook, matching
    research/window_repro.py).
    """
    station = "8531680"
    today = datetime.now().strftime("%Y%m%d")
    raw = _fetch_predictions(station, today, 48)
    if not raw:
        pytest.skip(f"No predictions returned for station {station}")
    predictions = _formatted(raw)

    first_tide_time = predictions[0]["time"]
    if first_tide_time.hour == 0 and first_tide_time.minute == 0:
        pytest.skip("First tide of the day lands exactly at midnight; nothing to reproduce")

    before_first_tide = first_tide_time - timedelta(minutes=15)
    last_tide, _next_tide, _following = select_tide_window(predictions, before_first_tide)
    assert last_tide is None, (
        "expected the pre-fix window to have no tide in the past before the "
        "day's first tide -- if this fails, the station's tide schedule may "
        "have changed such that it no longer reproduces the bug"
    )
