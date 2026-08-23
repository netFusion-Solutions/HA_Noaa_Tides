"""Pure tide-prediction selection logic, kept free of Home Assistant imports.

Isolated from noaa_api_client.py so the prediction-window regression test
(tests/test_prediction_window.py) can exercise it directly against live NOAA
data without needing a Home Assistant install.
"""

from __future__ import annotations

from datetime import datetime
from typing import TypedDict


class TidePrediction(TypedDict):
    """A single high/low tide prediction."""

    time: datetime
    type: str
    level: float


def select_tide_window(
    predictions: list[TidePrediction], now: datetime
) -> tuple[TidePrediction | None, TidePrediction | None, TidePrediction | None]:
    """Select the last, next, and following tide relative to ``now``.

    ``predictions`` need not be pre-sorted. Returns (last_tide, next_tide,
    following_tide); any of the three may be ``None`` if not present in the
    supplied predictions (following_tide in particular is optional -- it is
    only present when the window contains a third tide after next_tide).
    """
    formatted = sorted(predictions, key=lambda p: p["time"])

    last_tide: TidePrediction | None = None
    next_tide: TidePrediction | None = None
    following_tide: TidePrediction | None = None

    for pred in formatted:
        if pred["time"] <= now:
            last_tide = pred
        elif next_tide is None:
            next_tide = pred
        elif following_tide is None:
            following_tide = pred
            break

    return last_tide, next_tide, following_tide
