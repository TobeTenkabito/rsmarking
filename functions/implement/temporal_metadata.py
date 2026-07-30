"""Automatic acquisition-time and product metadata extraction for rasters.

Temporal identity is provenance metadata, not a property that can be inferred
reliably from pixel values.  This module therefore uses a confidence-ordered
resolver and always records where a value came from.  Upload time is
deliberately not used as an acquisition-time fallback.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date, datetime, time, timezone
import json
import os
import re
from typing import Any, Iterable


_MAX_SIDECAR_BYTES = 5 * 1024 * 1024

_ACQUISITION_KEYS = (
    "DATETIME",
    "ACQUISITIONDATETIME",
    "ACQUISITIONDATE",
    "ACQUISITIONTIME",
    "DATEACQUIRED",
    "SENSINGTIME",
    "SENSINGSTART",
    "PRODUCTSTARTTIME",
    "DATATAKESENSINGSTART",
    "STARTDATETIME",
    "TIFFTAGDATETIME",
    "TIMESERIESSTART",
)
_ACQUISITION_END_KEYS = (
    "ENDDATETIME",
    "SENSINGEND",
    "PRODUCTSTOPTIME",
    "PRODUCTENDTIME",
    "DATATAKESENSINGSTOP",
    "TIMESERIESEND",
)
_PLATFORM_KEYS = (
    "PLATFORM",
    "SPACECRAFTNAME",
    "SPACECRAFTID",
    "SATELLITE",
)
_SENSOR_KEYS = (
    "SENSOR",
    "INSTRUMENT",
    "INSTRUMENTNAME",
    "SENSORID",
)
_PRODUCT_KEYS = (
    "PRODUCTID",
    "LANDSATPRODUCTID",
    "PRODUCTURI",
    "GRANULEID",
)
_PROCESSING_LEVEL_KEYS = (
    "PROCESSINGLEVEL",
    "DATAPROCESSINGLEVEL",
    "PRODUCTTYPE",
)
_TILE_KEYS = (
    "TILEID",
    "MGRSTILE",
    "WRS_PATH_ROW",
    "PATHROW",
)


@dataclass
class TemporalMetadata:
    acquired_at: datetime | None = None
    acquired_at_end: datetime | None = None
    acquired_at_source: str = "unknown"
    acquired_at_confidence: float = 0.0
    platform: str | None = None
    sensor: str | None = None
    product_id: str | None = None
    processing_level: str | None = None
    tile_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def extract_temporal_metadata(
    file_path: str,
    *,
    source_name: str | None = None,
    dataset: Any | None = None,
) -> dict[str, Any]:
    """Resolve temporal metadata without inventing an acquisition timestamp."""
    result = TemporalMetadata()

    sidecar = _extract_sidecar_metadata(file_path, source_name)
    _merge_metadata(result, sidecar, overwrite=True)

    if dataset is not None:
        tags = _collect_dataset_tags(dataset)
        _merge_metadata(
            result,
            _metadata_from_tags(tags),
            overwrite=result.acquired_at is None,
        )

    filename = source_name or os.path.basename(file_path)
    _merge_metadata(
        result,
        _metadata_from_filename(filename),
        overwrite=result.acquired_at is None,
    )
    return result.to_dict()


def _merge_metadata(
    target: TemporalMetadata,
    incoming: TemporalMetadata | None,
    *,
    overwrite: bool,
) -> None:
    if incoming is None:
        return

    if incoming.acquired_at is not None and (overwrite or target.acquired_at is None):
        target.acquired_at = incoming.acquired_at
        target.acquired_at_end = incoming.acquired_at_end
        target.acquired_at_source = incoming.acquired_at_source
        target.acquired_at_confidence = incoming.acquired_at_confidence
    elif target.acquired_at_end is None and incoming.acquired_at_end is not None:
        target.acquired_at_end = incoming.acquired_at_end

    for field_name in (
        "platform",
        "sensor",
        "product_id",
        "processing_level",
        "tile_id",
    ):
        if getattr(target, field_name) is None:
            setattr(target, field_name, getattr(incoming, field_name))


def _collect_dataset_tags(dataset: Any) -> dict[str, str]:
    collected: dict[str, str] = {}
    namespaces: list[str | None] = [None]
    try:
        namespaces.extend(dataset.tag_namespaces())
    except Exception:
        pass

    for namespace in dict.fromkeys(namespaces):
        try:
            values = dataset.tags() if namespace is None else dataset.tags(ns=namespace)
        except Exception:
            continue
        for key, value in (values or {}).items():
            if value is None:
                continue
            normalized = _normalize_key(key)
            collected.setdefault(normalized, str(value).strip())
    return collected


def _metadata_from_tags(tags: dict[str, str]) -> TemporalMetadata:
    if not tags:
        return TemporalMetadata()

    acquired_text = _first_value(tags, _ACQUISITION_KEYS)
    if tags.get("DATEACQUIRED") and tags.get("SCENECENTERTIME"):
        acquired_text = _combine_date_and_time(
            tags["DATEACQUIRED"],
            tags.get("SCENECENTERTIME"),
        )
    acquired_at = _parse_datetime(acquired_text)
    acquired_at_end = _parse_datetime(_first_value(tags, _ACQUISITION_END_KEYS))

    is_time_series = tags.get("TIMESERIESANALYSIS", "").lower() == "true"
    source = (
        "derived_time_series"
        if acquired_at and is_time_series
        else "raster_tag"
        if acquired_at
        else "unknown"
    )
    confidence = 0.92 if acquired_at else 0.0
    return TemporalMetadata(
        acquired_at=acquired_at,
        acquired_at_end=acquired_at_end,
        acquired_at_source=source,
        acquired_at_confidence=confidence,
        platform=_clean_value(_first_value(tags, _PLATFORM_KEYS)),
        sensor=_clean_value(_first_value(tags, _SENSOR_KEYS)),
        product_id=_clean_value(_first_value(tags, _PRODUCT_KEYS)),
        processing_level=_clean_value(
            _first_value(tags, _PROCESSING_LEVEL_KEYS)
        ),
        tile_id=_clean_value(_first_value(tags, _TILE_KEYS)),
    )


def _extract_sidecar_metadata(
    file_path: str,
    source_name: str | None,
) -> TemporalMetadata | None:
    for candidate, kind in _sidecar_candidates(file_path, source_name):
        try:
            if kind == "stac":
                metadata = _metadata_from_stac(candidate)
            elif kind == "landsat_mtl":
                metadata = _metadata_from_landsat_mtl(candidate)
            else:
                metadata = _metadata_from_safe_xml(candidate)
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if metadata and (
            metadata.acquired_at is not None
            or metadata.platform
            or metadata.product_id
        ):
            return metadata
    return None


def _sidecar_candidates(
    file_path: str,
    source_name: str | None,
) -> Iterable[tuple[str, str]]:
    directory = os.path.dirname(os.path.abspath(file_path))
    disk_stem = os.path.splitext(os.path.basename(file_path))[0]
    source_stem = os.path.splitext(os.path.basename(source_name or ""))[0]
    seen: set[str] = set()

    def add(path: str, kind: str):
        absolute = os.path.abspath(path)
        if absolute in seen or not os.path.isfile(absolute):
            return
        try:
            if os.path.getsize(absolute) > _MAX_SIDECAR_BYTES:
                return
        except OSError:
            return
        seen.add(absolute)
        yield absolute, kind

    for stem in dict.fromkeys(value for value in (disk_stem, source_stem) if value):
        for suffix in (".stac.json", ".json"):
            yield from add(os.path.join(directory, stem + suffix), "stac")

    landsat_prefix = re.sub(
        r"_(?:SR_|ST_)?B\d+(?:\.[^.]+)?$",
        "",
        source_stem,
        flags=re.IGNORECASE,
    )
    if landsat_prefix and landsat_prefix != source_stem:
        yield from add(
            os.path.join(directory, landsat_prefix + "_MTL.txt"),
            "landsat_mtl",
        )

    for name in ("MTD_MSIL1C.xml", "MTD_MSIL2A.xml", "manifest.safe"):
        yield from add(os.path.join(directory, name), "sentinel_safe")


def _metadata_from_stac(path: str) -> TemporalMetadata:
    with open(path, "r", encoding="utf-8") as stream:
        payload = json.load(stream)
    if not isinstance(payload, dict):
        raise ValueError("STAC sidecar must be a JSON object")

    properties = payload.get("properties")
    if not isinstance(properties, dict):
        properties = {}
    acquired_at = _parse_datetime(
        properties.get("datetime") or properties.get("start_datetime")
    )
    acquired_at_end = _parse_datetime(properties.get("end_datetime"))
    instruments = properties.get("instruments")
    if isinstance(instruments, list):
        sensor = ", ".join(str(value) for value in instruments if value)
    else:
        sensor = instruments

    return TemporalMetadata(
        acquired_at=acquired_at,
        acquired_at_end=acquired_at_end,
        acquired_at_source="stac",
        acquired_at_confidence=1.0 if acquired_at else 0.0,
        platform=_clean_value(properties.get("platform")),
        sensor=_clean_value(sensor),
        product_id=_clean_value(
            properties.get("product_id")
            or properties.get("landsat:scene_id")
            or payload.get("id")
        ),
        processing_level=_clean_value(
            properties.get("processing:level")
            or properties.get("landsat:processing_level")
        ),
        tile_id=_clean_value(
            properties.get("mgrs:tile")
            or properties.get("landsat:wrs_path")
        ),
    )


def _metadata_from_landsat_mtl(path: str) -> TemporalMetadata:
    text = _read_small_text(path)
    values: dict[str, str] = {}
    for line in text.splitlines():
        match = re.match(r"\s*([A-Z0-9_]+)\s*=\s*(.*?)\s*$", line)
        if not match:
            continue
        values[_normalize_key(match.group(1))] = match.group(2).strip('" ')

    acquired_at = _parse_datetime(
        _combine_date_and_time(
            values.get("DATEACQUIRED"),
            values.get("SCENECENTERTIME"),
        )
    )
    return TemporalMetadata(
        acquired_at=acquired_at,
        acquired_at_source="landsat_mtl",
        acquired_at_confidence=1.0 if acquired_at else 0.0,
        platform=_clean_value(values.get("SPACECRAFTID")),
        sensor=_clean_value(values.get("SENSORID")),
        product_id=_clean_value(
            values.get("LANDSATPRODUCTID") or values.get("LANDSATSCENEID")
        ),
        processing_level=_clean_value(values.get("PROCESSINGLEVEL")),
        tile_id=_landsat_path_row(values),
    )


def _metadata_from_safe_xml(path: str) -> TemporalMetadata:
    text = _read_small_text(path)
    if "<!DOCTYPE" in text.upper() or "<!ENTITY" in text.upper():
        raise ValueError("Unsafe XML declaration")

    def xml_value(*names: str) -> str | None:
        for name in names:
            match = re.search(
                rf"<(?:[A-Za-z0-9_.-]+:)?{re.escape(name)}(?:\s[^>]*)?>"
                r"\s*([^<]+?)\s*</",
                text,
                flags=re.IGNORECASE,
            )
            if match:
                return match.group(1).strip()
        return None

    acquired_at = _parse_datetime(
        xml_value(
            "PRODUCT_START_TIME",
            "DATATAKE_SENSING_START",
            "SENSING_TIME",
        )
    )
    return TemporalMetadata(
        acquired_at=acquired_at,
        acquired_at_end=_parse_datetime(
            xml_value("PRODUCT_STOP_TIME", "DATATAKE_SENSING_STOP")
        ),
        acquired_at_source="sentinel_safe",
        acquired_at_confidence=1.0 if acquired_at else 0.0,
        platform=_clean_value(xml_value("SPACECRAFT_NAME")),
        sensor=_clean_value(xml_value("INSTRUMENT")),
        product_id=_clean_value(
            xml_value("PRODUCT_URI", "PRODUCT_URI_1C", "PRODUCT_URI_2A")
        ),
        processing_level=_clean_value(xml_value("PROCESSING_LEVEL")),
        tile_id=_clean_value(xml_value("TILE_ID")),
    )


def _metadata_from_filename(filename: str) -> TemporalMetadata:
    name = os.path.basename(filename or "")
    upper = name.upper()

    sentinel = re.search(
        r"\b(S2[AB])_MSIL(1C|2A)_(\d{8}T\d{6})",
        upper,
    )
    if sentinel:
        tile_match = re.search(r"_T(\d{2}[A-Z]{3})_", upper)
        return TemporalMetadata(
            acquired_at=_parse_datetime(sentinel.group(3)),
            acquired_at_source="sentinel_filename",
            acquired_at_confidence=0.9,
            platform=sentinel.group(1),
            sensor="MSI",
            product_id=os.path.splitext(name)[0],
            processing_level=f"L{sentinel.group(2)}",
            tile_id=f"T{tile_match.group(1)}" if tile_match else None,
        )

    landsat = re.search(
        r"\b(L[COTEM]\d{2})_(L[12][A-Z0-9]{2})_(\d{3})(\d{3})_(\d{8})_",
        upper,
    )
    if landsat:
        platform, sensor = _landsat_platform_sensor(landsat.group(1))
        return TemporalMetadata(
            acquired_at=_parse_datetime(landsat.group(5)),
            acquired_at_source="landsat_filename",
            acquired_at_confidence=0.9,
            platform=platform,
            sensor=sensor,
            product_id=os.path.splitext(name)[0],
            processing_level=landsat.group(2),
            tile_id=f"{landsat.group(3)}/{landsat.group(4)}",
        )

    timestamp = re.search(
        r"(?<!\d)((?:19|20)\d{2})[-_.]?(0[1-9]|1[0-2])"
        r"[-_.]?([0-2]\d|3[01])(?:[T_ -]?([0-2]\d)([0-5]\d)([0-5]\d))?(?!\d)",
        name,
    )
    if timestamp:
        value = "".join(part or "" for part in timestamp.groups())
        return TemporalMetadata(
            acquired_at=_parse_datetime(value),
            acquired_at_source="filename",
            acquired_at_confidence=0.55,
        )

    return TemporalMetadata()


def _parse_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        parsed = value
    elif isinstance(value, date):
        parsed = datetime.combine(value, time.min)
    else:
        text = str(value).strip().strip('"')
        if not text:
            return None
        normalized = text.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            parsed = None
            for fmt in (
                "%Y%m%dT%H%M%S",
                "%Y%m%d%H%M%S",
                "%Y%m%d",
                "%Y-%m-%d",
                "%Y/%m/%d",
                "%Y:%m:%d %H:%M:%S",
            ):
                try:
                    parsed = datetime.strptime(text, fmt)
                    break
                except ValueError:
                    continue
            if parsed is None:
                return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _combine_date_and_time(
    date_value: Any,
    time_value: Any,
) -> str | None:
    if not date_value:
        return None
    if not time_value:
        return str(date_value)
    cleaned_time = str(time_value).strip().rstrip("Z")
    return f"{str(date_value).strip()}T{cleaned_time}Z"


def _first_value(values: dict[str, str], keys: Iterable[str]) -> str | None:
    for key in keys:
        value = values.get(key)
        if value:
            return value
    return None


def _normalize_key(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]+", "", str(value).upper())


def _clean_value(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip().strip('"')
    return text or None


def _landsat_path_row(values: dict[str, str]) -> str | None:
    path = values.get("WRSPATH")
    row = values.get("WRSROW")
    if not path or not row:
        return None
    try:
        return f"{int(path):03d}/{int(row):03d}"
    except ValueError:
        return f"{path}/{row}"


def _landsat_platform_sensor(code: str) -> tuple[str, str]:
    mission = code[-2:]
    platform = f"Landsat-{int(mission)}" if mission.isdigit() else code
    prefix = code[:2]
    sensor = {
        "LC": "OLI_TIRS",
        "LO": "OLI",
        "LT": "TM",
        "LE": "ETM+",
        "LM": "MSS",
    }.get(prefix, prefix)
    return platform, sensor


def _read_small_text(path: str) -> str:
    if os.path.getsize(path) > _MAX_SIDECAR_BYTES:
        raise ValueError("Metadata sidecar is too large")
    with open(path, "r", encoding="utf-8", errors="replace") as stream:
        return stream.read(_MAX_SIDECAR_BYTES + 1)
