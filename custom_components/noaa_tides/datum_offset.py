"""Pure datum-correction arithmetic, kept free of Home Assistant imports.

Isolated from noaa_api_client.py so the datum-offset regression test
(tests/test_datum_correction.py) can exercise the actual computation
directly against live NOAA data without needing a Home Assistant install.
See NoaaApiClient.async_get_datum_offset for the two live lookups (station
datums, monthly mean sea level) this consumes.
"""

from __future__ import annotations

from typing import Any, TypedDict

from .data_constants import DECIMAL_PRECISION, METERS_TO_FEET_FACTOR


class DatumOffsetResult(TypedDict):
    """Result of compute_datum_offset()."""

    offset: float
    source: str
    epoch: str


class DatumLookupError(Exception):
    """Raised when the datums.json or monthly_mean payload is unusable."""


def compute_datum_offset(
    datums_json: dict[str, Any],
    monthly_mean_rows: list[dict[str, Any]],
    unit_system: str,
) -> DatumOffsetResult:
    """Compute offset = MSL_observed (latest monthly_mean) - MSL_epoch.

    Args:
        datums_json: Parsed response from the station's datums.json endpoint.
        monthly_mean_rows: The "data" list from a monthly_mean datagetter
            response, in NOAA's chronological order; the last row is used
            as the most recent month available.
        unit_system: "Metric" or "Imperial" -- must match the units the
            monthly_mean rows were requested in; datums.json has no units
            param and is converted to match.

    Returns:
        DatumOffsetResult: offset (in unit_system's units), source (e.g.
        "monthly_mean 2026-07"), and epoch (e.g. "1983-2001").

    Raises:
        DatumLookupError: if either payload doesn't contain usable data.

    """
    msl_epoch_raw: float | None = None
    for datum in datums_json.get("datums", []):
        if datum.get("name") == "MSL":
            msl_epoch_raw = float(datum["value"])
            break

    if msl_epoch_raw is None:
        raise DatumLookupError("No MSL datum published for this station")

    epoch = datums_json.get("epoch", "unknown")
    # datums.json has no units param and is documented as feet, but convert
    # generically off the reported "units" field rather than assuming.
    epoch_units = datums_json.get("units", "feet")
    if epoch_units == "feet" and unit_system == "Metric":
        msl_epoch = msl_epoch_raw / METERS_TO_FEET_FACTOR
    elif epoch_units == "meters" and unit_system != "Metric":
        msl_epoch = msl_epoch_raw * METERS_TO_FEET_FACTOR
    else:
        msl_epoch = msl_epoch_raw

    if not monthly_mean_rows:
        raise DatumLookupError("No monthly_mean data available")

    # NOAA returns monthly_mean rows in chronological order; the last row
    # is the most recent month available (publication lags by roughly a
    # month).
    latest = monthly_mean_rows[-1]
    try:
        msl_observed = float(latest["MSL"])
        year = int(latest["year"])
        month = int(latest["month"])
    except (KeyError, ValueError, TypeError) as err:
        raise DatumLookupError(f"Malformed monthly_mean data: {err}") from err

    offset = round(msl_observed - msl_epoch, DECIMAL_PRECISION)

    return DatumOffsetResult(
        offset=offset,
        source=f"monthly_mean {year:04d}-{month:02d}",
        epoch=epoch,
    )
