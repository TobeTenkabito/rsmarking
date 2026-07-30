"""Automatic, non-blocking grouping of raster records into series candidates."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Iterable


def build_time_series_candidates(records: Iterable[Any]) -> list[dict[str, Any]]:
    groups: dict[str, list[Any]] = {}
    for record in records:
        groups.setdefault(_candidate_key(record), []).append(record)

    candidates = [
        _candidate_payload(key, members)
        for key, members in groups.items()
    ]
    return sorted(
        candidates,
        key=lambda candidate: (
            -candidate["input_count"],
            -candidate["dated_input_count"],
            candidate["candidate_id"],
        ),
    )


def _candidate_payload(key: str, members: list[Any]) -> dict[str, Any]:
    ordered = sorted(
        enumerate(members),
        key=lambda entry: (
            _value(entry[1], "acquired_at") is None,
            _value(entry[1], "acquired_at") or "",
            entry[0],
        ),
    )
    ordered_members = [entry[1] for entry in ordered]
    dates = [
        _value(record, "acquired_at")
        for record in ordered_members
        if _value(record, "acquired_at") is not None
    ]
    date_sources: dict[str, int] = {}
    for record in ordered_members:
        source = _value(record, "acquired_at_source") or "unknown"
        date_sources[source] = date_sources.get(source, 0) + 1

    unknown_count = len(ordered_members) - len(dates)
    low_confidence_count = sum(
        _value(record, "acquired_at") is not None
        and float(_value(record, "acquired_at_confidence") or 0.0) < 0.75
        for record in ordered_members
    )
    distinct_grids = {
        _grid_signature(record)
        for record in ordered_members
    }
    duplicate_date_count = len(dates) - len(set(dates))
    warnings: list[str] = []
    if unknown_count:
        warnings.append(
            f"{unknown_count} raster(s) have unknown acquisition dates."
        )
    if low_confidence_count:
        warnings.append(
            f"{low_confidence_count} raster date(s) came from low-confidence "
            "filename inference."
        )
    if len(distinct_grids) > 1:
        warnings.append(
            f"{len(distinct_grids) - 1} non-reference grid(s) will be "
            "automatically aligned."
        )
    if duplicate_date_count:
        warnings.append(
            f"{duplicate_date_count} duplicate acquisition timestamp(s) are "
            "present."
        )

    reference = ordered_members[0]
    payload = {
        "candidate_id": hashlib.sha256(key.encode("utf-8")).hexdigest()[:16],
        "raster_ids": [
            int(_value(record, "index_id"))
            for record in ordered_members
        ],
        "input_count": len(ordered_members),
        "dated_input_count": len(dates),
        "date_coverage": len(dates) / len(ordered_members),
        "acquisition_start": min(dates).isoformat() if dates else None,
        "acquisition_end": max(dates).isoformat() if dates else None,
        "date_sources": date_sources,
        "platform": _value(reference, "platform"),
        "sensor": _value(reference, "sensor"),
        "processing_level": _value(reference, "processing_level"),
        "tile_id": _value(reference, "tile_id"),
        "band_count": int(_value(reference, "bands") or 0),
        "automatic_alignment": len(distinct_grids) > 1,
        "warnings": warnings,
    }
    payload["suggested_operations"] = _suggested_operations(payload)
    return payload


def _candidate_key(record: Any) -> str:
    product = {
        "platform": _normalized(record, "platform"),
        "sensor": _normalized(record, "sensor"),
        "processing_level": _normalized(record, "processing_level"),
        "tile_id": _normalized(record, "tile_id"),
        "bands": int(_value(record, "bands") or 0),
    }
    if any(product[field] for field in product if field != "bands"):
        value = {"kind": "product", **product}
        if not product["tile_id"]:
            value["spatial"] = _spatial_signature(record)
    else:
        value = {
            "kind": "grid",
            "spatial": _spatial_signature(record),
            "bands": product["bands"],
        }
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _grid_signature(record: Any) -> str:
    bounds = _number_sequence(_value(record, "bounds"))
    values = (
        _normalized(record, "crs"),
        int(_value(record, "width") or 0),
        int(_value(record, "height") or 0),
        _rounded(_value(record, "resolution_x")),
        _rounded(_value(record, "resolution_y")),
        tuple(_rounded(value) for value in bounds[:4]),
    )
    return "|".join(str(value) for value in values)


def _spatial_signature(record: Any) -> str:
    bounds = _number_sequence(_value(record, "bounds_wgs84"))
    if len(bounds) >= 4:
        west, south, east, north = bounds[:4]
        values = (
            round((west + east) / 2.0, 3),
            round((south + north) / 2.0, 3),
            round(abs(east - west), 3),
            round(abs(north - south), 3),
        )
        return "wgs84|" + "|".join(str(value) for value in values)

    center = _number_sequence(_value(record, "center"))
    if len(center) >= 2:
        return (
            f"center|{round(center[0], 3)}|{round(center[1], 3)}|"
            f"{_grid_signature(record)}"
        )
    return f"grid|{_grid_signature(record)}"


def _suggested_operations(candidate: dict[str, Any]) -> list[str]:
    count = candidate["input_count"]
    dated = candidate["dated_input_count"]
    operations = ["maximum_composite", "median_composite"]
    if dated:
        operations.extend(["monthly_composite", "annual_composite"])
    if count >= 2:
        operations.extend(
            [
                "moving_window_smoothing",
                "trend",
                "seasonality",
                "phenology",
            ]
        )
    if count >= 3:
        operations.append("savitzky_golay")
    return operations


def _value(record: Any, field: str) -> Any:
    if isinstance(record, dict):
        return record.get(field)
    return getattr(record, field, None)


def _normalized(record: Any, field: str) -> str:
    return str(_value(record, field) or "").strip().lower()


def _rounded(value: Any) -> float:
    try:
        return round(float(value), 9)
    except (TypeError, ValueError):
        return 0.0


def _number_sequence(value: Any) -> list[float]:
    if not isinstance(value, (list, tuple)):
        return []
    result: list[float] = []
    for item in value:
        try:
            result.append(float(item))
        except (TypeError, ValueError):
            return []
    return result
