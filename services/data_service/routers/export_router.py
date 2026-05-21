import csv
import json
import logging
import os
import re
import shutil
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.background import BackgroundTask

from services.data_service.bridges.vector_bridge import (
    internal_fetch_features,
    internal_fetch_fields,
)
from services.data_service.crud.raster_crud import RasterCRUD
from services.data_service.crud.raster_field_crud import RasterFieldCRUD
from services.data_service.database import get_db


logger = logging.getLogger("data_service.export")
router = APIRouter(tags=["Export"])

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", "..", ".."))
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")


class VectorLayerExportRef(BaseModel):
    id: str
    name: str | None = None


class WorkspaceExportRequest(BaseModel):
    filename: str = Field(default="RSMarking_Export")
    raster_ids: list[int] = Field(default_factory=list)
    vector_layers: list[VectorLayerExportRef] = Field(default_factory=list)


@router.post("/export/workspace-file")
async def export_workspace_file(
    payload: WorkspaceExportRequest,
    db: AsyncSession = Depends(get_db),
):
    raster_ids = _dedupe(payload.raster_ids)
    vector_layers = _dedupe_layers(payload.vector_layers)

    if not raster_ids and not vector_layers:
        raise HTTPException(
            status_code=400,
            detail="No active raster or visible vector layers were selected for export.",
        )

    package_name = _safe_filename(payload.filename, "RSMarking_Export", max_length=80)
    staging_dir = tempfile.mkdtemp(prefix="rsmarking_export_")
    zip_path = os.path.join(staging_dir, f"{package_name}.zip")

    manifest: dict[str, Any] = {
        "format": "RSMarking GIS ZIP",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "vectors": [],
        "rasters": [],
        "warnings": [],
    }

    try:
        if vector_layers:
            manifest["vectors"] = await _export_vector_layers(
                Path(staging_dir),
                vector_layers,
                manifest["warnings"],
            )

        if raster_ids:
            manifest["rasters"] = await _export_rasters(
                Path(staging_dir),
                raster_ids,
                db,
                manifest["warnings"],
            )

        if not manifest["vectors"] and not manifest["rasters"]:
            raise HTTPException(status_code=404, detail="No exportable GIS content was found.")

        _write_json(Path(staging_dir) / "manifest.json", manifest)
        _write_readme(Path(staging_dir) / "README.txt")
        _zip_directory(Path(staging_dir), Path(zip_path))

    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise

    return FileResponse(
        zip_path,
        media_type="application/zip",
        filename=f"{package_name}.zip",
        background=BackgroundTask(shutil.rmtree, staging_dir, ignore_errors=True),
    )


async def _export_vector_layers(
    root: Path,
    layers: list[VectorLayerExportRef],
    warnings: list[str],
) -> list[dict[str, Any]]:
    vector_dir = root / "vectors"
    vector_dir.mkdir(parents=True, exist_ok=True)

    exported = []
    used_layer_names: set[str] = set()
    for layer in layers:
        layer_name = layer.name or f"layer_{layer.id}"
        safe_layer = _unique_name(
            _safe_filename(layer_name, f"layer_{layer.id}", max_length=60),
            used_layer_names,
            max_length=60,
        )

        try:
            features = await internal_fetch_features(layer.id)
            fields = await internal_fetch_fields(layer.id)
        except HTTPException as exc:
            warnings.append(f"Vector layer {layer_name} skipped: {exc.detail}")
            continue

        field_defs = _build_vector_field_defs(fields, features)
        mapping_rows = [
            {
                "original_name": f["source_name"],
                "dbf_name": f["dbf_name"],
                "alias": f["alias"],
                "type": f["type"],
            }
            for f in field_defs
        ]

        geojson_path = vector_dir / f"{safe_layer}.geojson"
        _write_json(
            geojson_path,
            {
                "type": "FeatureCollection",
                "name": layer_name,
                "features": features,
                "rsmarking_fields": mapping_rows,
            },
        )

        mapping_path = vector_dir / f"{safe_layer}_field_mapping.csv"
        _write_csv(
            mapping_path,
            ["original_name", "dbf_name", "alias", "type"],
            mapping_rows,
        )

        shapefiles = _write_shapefiles(
            vector_dir,
            safe_layer,
            features,
            field_defs,
            warnings,
        )

        exported.append(
            {
                "layer_id": layer.id,
                "name": layer_name,
                "feature_count": len(features),
                "geojson": _relative(root, geojson_path),
                "field_mapping": _relative(root, mapping_path),
                "shapefiles": [_relative(root, path) for path in shapefiles],
            }
        )

    return exported


async def _export_rasters(
    root: Path,
    raster_ids: list[int],
    db: AsyncSession,
    warnings: list[str],
) -> list[dict[str, Any]]:
    raster_dir = root / "rasters"
    raster_dir.mkdir(parents=True, exist_ok=True)

    exported = []
    field_crud = RasterFieldCRUD(db)

    for raster_id in raster_ids:
        record = await RasterCRUD.get_raster_by_index_id(db, int(raster_id))
        if not record:
            warnings.append(f"Raster {raster_id} skipped: record not found.")
            continue

        source_path = _resolve_raster_file_path(record.cog_path) or _resolve_raster_file_path(record.file_path)
        if not source_path:
            warnings.append(f"Raster {record.index_id} skipped: source file not found.")
            continue

        source = Path(source_path)
        extension = source.suffix if source.suffix else ".tif"
        safe_name = _safe_filename(source.stem or record.file_name, f"raster_{record.index_id}", max_length=60)
        raster_path = _unique_path(raster_dir / f"{safe_name}{extension}")
        shutil.copy2(source, raster_path)

        fields = await field_crud.get_by_raster(record.index_id)
        attr_rows = _build_raster_attribute_rows(record, fields)
        attr_path = raster_dir / f"{raster_path.stem}_attributes.csv"
        _write_csv(
            attr_path,
            ["field_name", "field_alias", "field_type", "value", "scope"],
            attr_rows,
        )

        exported.append(
            {
                "index_id": record.index_id,
                "file_name": record.file_name,
                "raster": _relative(root, raster_path),
                "attributes": _relative(root, attr_path),
                "crs": record.crs,
                "bounds_wgs84": record.bounds_wgs84,
            }
        )

    return exported


def _write_shapefiles(
    vector_dir: Path,
    safe_layer: str,
    features: list[dict[str, Any]],
    field_defs: list[dict[str, Any]],
    warnings: list[str],
) -> list[Path]:
    if not features:
        return []

    try:
        import fiona
    except Exception as exc:
        warnings.append(f"Shapefile export skipped for {safe_layer}: Fiona unavailable ({exc}).")
        return []

    groups: dict[str, list[dict[str, Any]]] = {}
    for feature in features:
        geometry = feature.get("geometry") or {}
        geom_type = geometry.get("type")
        if not geom_type:
            warnings.append(f"Feature {feature.get('id', '')} skipped: missing geometry.")
            continue
        groups.setdefault(geom_type, []).append(feature)

    schema_props = {field["dbf_name"]: field["fiona_type"] for field in field_defs}
    written: list[Path] = []

    for geom_type, group in groups.items():
        suffix = _safe_filename(geom_type.lower(), "geometry", max_length=24)
        shp_path = _unique_path(vector_dir / f"{safe_layer}_{suffix}.shp")
        schema = {"geometry": geom_type, "properties": schema_props}

        try:
            with fiona.open(
                shp_path,
                mode="w",
                driver="ESRI Shapefile",
                crs="EPSG:4326",
                schema=schema,
                encoding="UTF-8",
            ) as sink:
                for feature in group:
                    sink.write(
                        {
                            "geometry": feature.get("geometry"),
                            "properties": _feature_dbf_properties(feature, field_defs),
                        }
                    )
            shp_path.with_suffix(".cpg").write_text("UTF-8", encoding="utf-8")
            written.append(shp_path)
        except Exception as exc:
            warnings.append(f"Shapefile export failed for {safe_layer} ({geom_type}): {exc}")

    return written


def _build_vector_field_defs(
    fields: list[dict[str, Any]],
    features: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    source_defs: list[dict[str, Any]] = [
        {
            "field_name": "__feature_id",
            "field_alias": "Feature ID",
            "field_type": "string",
            "field_order": -1,
            "default_val": "",
        }
    ]

    if fields:
        source_defs.extend(
            sorted(
                fields,
                key=lambda field: (
                    field.get("field_order") if field.get("field_order") is not None else 9999,
                    field.get("field_name") or "",
                ),
            )
        )
        known_names = {str(field.get("field_name") or "") for field in source_defs}
        extra_names = []
        for feature in features:
            for name in (feature.get("properties") or {}).keys():
                if name not in known_names:
                    known_names.add(name)
                    extra_names.append(name)
        source_defs.extend(
            {
                "field_name": name,
                "field_alias": name,
                "field_type": _infer_field_type(features, name),
                "field_order": 9000 + idx,
                "default_val": "",
            }
            for idx, name in enumerate(extra_names)
        )
    else:
        inferred_names = []
        seen = set()
        for feature in features:
            for name in (feature.get("properties") or {}).keys():
                if name not in seen:
                    seen.add(name)
                    inferred_names.append(name)
        source_defs.extend(
            {
                "field_name": name,
                "field_alias": name,
                "field_type": _infer_field_type(features, name),
                "field_order": idx,
                "default_val": "",
            }
            for idx, name in enumerate(inferred_names)
        )

    if not any(field.get("field_name") == "category" for field in source_defs):
        source_defs.append(
            {
                "field_name": "category",
                "field_alias": "category",
                "field_type": "string",
                "field_order": 9998,
                "default_val": "",
            }
        )

    used_names: set[str] = set()
    result = []
    for field in source_defs:
        source_name = str(field.get("field_name") or "field")
        dbf_name = _dbf_field_name(source_name, used_names)
        field_type = str(field.get("field_type") or "string").lower()
        result.append(
            {
                "source_name": source_name,
                "dbf_name": dbf_name,
                "alias": field.get("field_alias") or source_name,
                "type": field_type,
                "default": field.get("default_val"),
                "fiona_type": _fiona_field_type(field_type),
            }
        )

    return result


def _feature_dbf_properties(
    feature: dict[str, Any],
    field_defs: list[dict[str, Any]],
) -> dict[str, Any]:
    source_props = feature.get("properties") or {}
    props = {}

    for field in field_defs:
        source_name = field["source_name"]
        if source_name == "__feature_id":
            value = feature.get("id", "")
        else:
            value = source_props.get(source_name, field.get("default"))
        props[field["dbf_name"]] = _coerce_dbf_value(value, field["type"])

    return props


def _build_raster_attribute_rows(record: Any, fields: list[Any]) -> list[dict[str, Any]]:
    resolution = ""
    if record.resolution_x is not None or record.resolution_y is not None:
        resolution = f"{record.resolution_x or ''}, {record.resolution_y or ''}"

    system_rows = [
        ("index_id", "Index ID", "number", record.index_id),
        ("file_name", "File name", "string", record.file_name),
        ("width", "Width (px)", "number", record.width),
        ("height", "Height (px)", "number", record.height),
        ("bands", "Bands", "number", record.bands),
        ("crs", "CRS", "string", record.crs),
        ("data_type", "Data type", "string", record.data_type),
        ("resolution", "Resolution", "string", resolution),
        ("bounds", "Bounds", "string", _json_text(record.bounds)),
        ("bounds_wgs84", "Bounds WGS84", "string", _json_text(record.bounds_wgs84)),
        ("bundle_id", "Bundle ID", "string", record.bundle_id),
    ]

    rows = [
        {
            "field_name": name,
            "field_alias": alias,
            "field_type": field_type,
            "value": "" if value is None else value,
            "scope": "system",
        }
        for name, alias, field_type, value in system_rows
        if value not in (None, "")
    ]

    for field in fields:
        rows.append(
            {
                "field_name": field.field_name,
                "field_alias": field.field_alias or field.field_name,
                "field_type": field.field_type,
                "value": field.default_val or "",
                "scope": "system" if field.is_system else "custom",
            }
        )

    return rows


def _resolve_raster_file_path(path: str | None) -> str | None:
    if not path:
        return None
    if os.path.exists(path):
        return path
    if path.startswith("/data/"):
        local = os.path.join(COG_DIR, os.path.basename(path))
        if os.path.exists(local):
            return local
    return None


def _infer_field_type(features: list[dict[str, Any]], name: str) -> str:
    for feature in features:
        value = (feature.get("properties") or {}).get(name)
        if value is None:
            continue
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, (int, float)):
            return "number"
        return "string"
    return "string"


def _fiona_field_type(field_type: str) -> str:
    if field_type == "number":
        return "float"
    return "str:254"


def _coerce_dbf_value(value: Any, field_type: str) -> Any:
    if value is None:
        return None
    if field_type == "number":
        try:
            return float(value)
        except (TypeError, ValueError):
            return None
    if field_type == "boolean":
        return "true" if value is True or str(value).lower() == "true" else "false"
    if isinstance(value, (dict, list)):
        value = json.dumps(value, ensure_ascii=False)
    return str(value)[:254]


def _dbf_field_name(source_name: str, used_names: set[str]) -> str:
    ascii_name = source_name.encode("ascii", "ignore").decode("ascii")
    base = re.sub(r"[^A-Za-z0-9_]+", "_", ascii_name).strip("_").upper()
    if not base:
        base = "FIELD"
    if not base[0].isalpha():
        base = f"F_{base}"

    candidate = base[:10]
    counter = 1
    while candidate in used_names:
        suffix = f"_{counter}"
        candidate = f"{base[:10 - len(suffix)]}{suffix}"
        counter += 1

    used_names.add(candidate)
    return candidate


def _safe_filename(value: Any, fallback: str, max_length: int = 80) -> str:
    text = str(value or "").strip()
    text = re.sub(r'[\\/:*?"<>|]+', "_", text)
    text = re.sub(r"\s+", "_", text).strip("._ ")
    return (text[:max_length] or fallback).strip("._ ") or fallback


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    stem = path.stem
    suffix = path.suffix
    parent = path.parent
    counter = 2
    while True:
        candidate = parent / f"{stem}_{counter}{suffix}"
        if not candidate.exists():
            return candidate
        counter += 1


def _unique_name(name: str, used_names: set[str], max_length: int = 80) -> str:
    candidate = name[:max_length]
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    counter = 2
    while True:
        suffix = f"_{counter}"
        candidate = f"{name[:max_length - len(suffix)]}{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        counter += 1


def _dedupe(values: list[int]) -> list[int]:
    seen = set()
    result = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def _dedupe_layers(layers: list[VectorLayerExportRef]) -> list[VectorLayerExportRef]:
    seen = set()
    result = []
    for layer in layers:
        if layer.id in seen:
            continue
        seen.add(layer.id)
        result.append(layer)
    return result


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )


def _write_csv(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _write_readme(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "RSMarking GIS export package",
                "",
                "vectors/: GeoJSON plus ESRI Shapefile exports for visible vector layers.",
                "rasters/: GeoTIFF/COG copies plus attribute CSV sidecars for active rasters.",
                "manifest.json lists exported files and any warnings.",
                "",
                "Open the .shp, .geojson, or .tif files directly in QGIS or ArcGIS.",
            ]
        ),
        encoding="utf-8",
    )


def _zip_directory(root: Path, zip_path: Path) -> None:
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in root.rglob("*"):
            if not file_path.is_file() or file_path == zip_path:
                continue
            archive.write(file_path, _relative(root, file_path))


def _relative(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _json_text(value: Any) -> str:
    if value is None:
        return ""
    return json.dumps(value, ensure_ascii=False)
