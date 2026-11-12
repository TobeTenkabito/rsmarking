"""Persist sandbox geometry without routing its coordinate arrays through the model."""

import hashlib
import json
import math
from collections import Counter

from pyproj import Geod
from shapely.geometry import shape

from . import artifacts


def summarize_geojson(document: dict, expected_bbox: list[float] | None = None) -> dict:
    if not isinstance(document, dict) or document.get("type") != "FeatureCollection":
        raise ValueError("Expected a WGS84 GeoJSON FeatureCollection")
    if document.get("crs"):
        name = document["crs"].get("properties", {}).get("name", "")
        if name not in {"EPSG:4326", "urn:ogc:def:crs:OGC:1.3:CRS84"}:
            raise ValueError("GeoJSON coordinates must use WGS84 longitude/latitude")
    features = document.get("features")
    if not isinstance(features, list) or len(features) > 10000:
        raise ValueError("GeoJSON must contain at most 10,000 features")
    if expected_bbox is not None:
        west, south, east, north = expected_bbox
        if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
            raise ValueError("Expected bbox must be ordered WGS84 bounds")
    types = Counter()
    bounds = []
    invalid = empty = outside = 0
    length = 0.0
    geod = Geod(ellps="WGS84")
    for feature in features:
        if not isinstance(feature, dict) or feature.get("type") != "Feature":
            raise ValueError("GeoJSON entries must be Features")
        geometry = shape(feature["geometry"]) if feature.get("geometry") else None
        if geometry is None or geometry.is_empty:
            empty += 1
            continue
        types[geometry.geom_type] += 1
        invalid += not geometry.is_valid
        left, bottom, right, top = geometry.bounds
        if not all(math.isfinite(value) for value in geometry.bounds):
            raise ValueError("GeoJSON contains non-finite coordinates")
        if not (-180 <= left <= right <= 180 and -90 <= bottom <= top <= 90):
            raise ValueError("GeoJSON coordinates are outside WGS84 longitude/latitude bounds")
        bounds.append(geometry.bounds)
        if expected_bbox is not None:
            outside += (
                left < west - 1e-9
                or bottom < south - 1e-9
                or right > east + 1e-9
                or top > north + 1e-9
            )
        if geometry.geom_type in {"LineString", "MultiLineString"}:
            length += geod.geometry_length(geometry)
    extent = None
    if bounds:
        extent = [
            min(b[0] for b in bounds),
            min(b[1] for b in bounds),
            max(b[2] for b in bounds),
            max(b[3] for b in bounds),
        ]
    return {
        "feature_count": len(features),
        "geometry_types": dict(types),
        "bbox": extent,
        "empty_count": empty,
        "invalid_count": invalid,
        "line_length_m": round(length, 3),
        "outside_expected_bbox": outside if expected_bbox is not None else None,
        "properties_preview": [
            json.dumps(feature.get("properties", {}), ensure_ascii=False)[:1000]
            for feature in features[:3]
        ],
    }


def create_geojson_artifact(filename: str, document: dict) -> dict:
    data = json.dumps(document, ensure_ascii=False, allow_nan=False).encode("utf-8")
    if len(data) > 5 * 1024 * 1024:
        raise ValueError("Sandbox GeoJSON exceeds 5 MiB")
    summary = summarize_geojson(document)
    artifact = artifacts._write_artifact(
        filename=artifacts._safe_filename(filename, ".geojson"),
        data=data,
        mime_type="application/geo+json",
        kind="file",
    )
    return {**artifact, "geometry_summary": summary}


def inspect_geojson_artifact(artifact_id: str, expected_bbox: list[float] | None = None) -> dict:
    metadata, path = artifacts.get_artifact(artifact_id)
    if path.suffix.lower() not in {".json", ".geojson"} or path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("Inspection requires a JSON/GeoJSON artifact no larger than 5 MiB")
    data = path.read_bytes()
    summary = summarize_geojson(json.loads(data), expected_bbox)
    return {
        **metadata,
        "size": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        **summary,
    }


def inspect_raster_boundary(
    artifact_id: str, raster_path: str, threshold: float, band: int = 1
) -> dict:
    """Sample actual raster pixels on both sides of saved lines; bounded, read-only evidence."""
    import numpy as np
    import rasterio
    from pyproj import Transformer
    from shapely.ops import transform

    _, path = artifacts.get_artifact(artifact_id)
    document = json.loads(path.read_bytes())
    with rasterio.open(raster_path) as raster:
        if not raster.crs or not raster.crs.is_projected or raster.crs.linear_units != "metre":
            raise ValueError("Boundary sampling currently requires a raster projected in metres")
        if not 1 <= band <= raster.count or not math.isfinite(threshold):
            raise ValueError("Invalid raster band or threshold")
        project = Transformer.from_crs(4326, raster.crs, always_xy=True).transform
        lines = []
        for feature in document["features"]:
            geometry = shape(feature["geometry"]) if feature.get("geometry") else None
            if geometry is None or geometry.is_empty:
                continue
            if geometry.geom_type not in {"LineString", "MultiLineString"}:
                continue
            projected = transform(project, geometry)
            lines.extend(
                projected.geoms if projected.geom_type == "MultiLineString" else [projected]
            )
        lines = [line for line in lines if line.length > 0]
        if not lines:
            return {"sample_count": 0, "valid_pair_count": 0, "opposite_class_fraction": None}
        lengths = np.array([line.length for line in lines])
        cumulative = np.cumsum(lengths)
        offset = 1.25 * max(abs(raster.res[0]), abs(raster.res[1]))
        positions = (np.arange(200) + 0.5) / 200 * cumulative[-1]
        pairs = []
        for position in positions:
            index = int(np.searchsorted(cumulative, position))
            line = lines[index]
            distance = position - (cumulative[index - 1] if index else 0)
            start = line.interpolate(max(0, distance - offset / 2))
            end = line.interpolate(min(line.length, distance + offset / 2))
            dx, dy = end.x - start.x, end.y - start.y
            norm = math.hypot(dx, dy)
            if not norm:
                continue
            center = line.interpolate(distance)
            nx, ny = -dy / norm * offset, dx / norm * offset
            pairs.extend([(center.x + nx, center.y + ny), (center.x - nx, center.y - ny)])
        values = np.ma.vstack(list(raster.sample(pairs, indexes=band, masked=True))).reshape(-1, 2)
        valid = ~np.ma.getmaskarray(values).any(axis=1) & np.isfinite(values.data).all(axis=1)
        opposite = (values.data[:, 0] > threshold) != (values.data[:, 1] > threshold)
        return {
            "sample_count": len(values),
            "valid_pair_count": int(valid.sum()),
            "opposite_class_fraction": float(opposite[valid].mean()) if valid.any() else None,
            "threshold": threshold,
            "offset_m": offset,
            "method": "200 length-weighted paired samples of actual raster pixels across saved line normals",
            "limitation": "Checks spectral water-land adjacency, not ground-truth coastline accuracy.",
        }
