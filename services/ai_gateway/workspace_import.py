"""Register generated spatial artifacts as new workspace data, without host paths."""

import asyncio
import hashlib
import json
import shutil
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, insert, select, text

from . import artifacts
from .vector_artifacts import summarize_geojson


class WorkspaceImportArgs(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    artifact_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    name: str = Field(min_length=1, max_length=180)
    project_id: UUID | None = Field(default=None, description="Existing vector project; omitted creates/uses Agent outputs.")
    source_raster_index_id: int | None = Field(default=None, gt=0)


async def import_generated_artifact(args, db, vector_db):
    metadata, path = artifacts.get_artifact(args.artifact_id)
    suffix = path.suffix.lower()
    if suffix in {".json", ".geojson"}:
        document, summary = await asyncio.to_thread(_read_geojson, path)
        if args.source_raster_index_id is not None:
            from services.data_service.models import RasterMetadata

            source = await db.scalar(select(RasterMetadata.index_id).where(
                RasterMetadata.index_id == args.source_raster_index_id
            ))
            if source is None:
                raise ValueError("Source raster does not exist")
        result = await _import_vector(args, document, summary, vector_db)
    elif suffix in {".tif", ".tiff"}:
        if args.project_id is not None:
            raise ValueError("A raster is imported into the imagery catalog, not a vector project")
        result = await _import_raster(args, path, db)
    else:
        raise ValueError("Workspace layers require WGS84 GeoJSON or georeferenced GeoTIFF. Documents and tables remain downloadable artifacts.")
    return {"status": "success", "workspace_import": result, "artifact": metadata}


def _read_geojson(path):
    if path.stat().st_size > 5 * 1024 * 1024:
        raise ValueError("Workspace GeoJSON cannot exceed 5 MiB")
    document = json.loads(path.read_bytes())
    # Reject non-finite properties as well as invalid geometry before any DB write.
    json.dumps(document, allow_nan=False)
    summary = summarize_geojson(document)
    if not summary["feature_count"] or summary["empty_count"] or summary["invalid_count"]:
        raise ValueError("Workspace GeoJSON must contain nonempty, valid geometries")
    for feature in document["features"]:
        if not isinstance(feature.get("properties", {}), (dict, type(None))):
            raise ValueError("Feature properties must be an object or null")
        category = (feature.get("properties") or {}).get("category")
        if category is not None and (not isinstance(category, str) or len(category) > 100):
            raise ValueError("The category property must be text of at most 100 characters")
    return document, summary


async def _lock_import(db):
    # Serialize short imports across gateway workers, including default-project creation.
    await db.execute(text("SELECT pg_advisory_xact_lock(731948210)"))


async def _import_vector(args, document, summary, db):
    from geoalchemy2.shape import from_shape
    from shapely.geometry import shape
    from services.annotation_service.models.feature import Feature, Layer, LayerField, Project

    project_id = args.project_id or uuid5(NAMESPACE_URL, "rsmarking:agent-output-project")
    layer_id = uuid5(NAMESPACE_URL, f"rsmarking:artifact:{args.artifact_id}:{project_id}")
    properties = [feature.get("properties") or {} for feature in document["features"]]
    fields = sorted({key for values in properties for key in values})
    if len(fields) > 100 or any(not key or len(key) > 128 for key in fields):
        raise ValueError("Imported features support at most 100 named fields of 128 characters")
    try:
        await _lock_import(db)
        existing = await db.get(Layer, layer_id)
        if existing is not None:
            count = await db.scalar(select(func.count()).select_from(Feature).where(Feature.layer_id == layer_id))
            await db.commit()
            return {"data_type": "vector", "project_id": str(project_id), "layer_id": str(layer_id),
                    "name": existing.name, "feature_count": count, "reused": True}
        project = await db.get(Project, project_id)
        if project is None:
            if args.project_id is not None:
                raise ValueError("Vector project does not exist")
            db.add(Project(id=project_id, name="Agent outputs"))
            await db.flush()
        db.add(Layer(id=layer_id, project_id=project_id, name=args.name,
                     source_raster_index_id=args.source_raster_index_id))
        await db.flush()
        for order, key in enumerate(fields):
            values = [row[key] for row in properties if row.get(key) is not None]
            field_type = "string"
            if values and all(isinstance(value, bool) for value in values):
                field_type = "boolean"
            elif values and all(isinstance(value, (int, float)) and not isinstance(value, bool) for value in values):
                field_type = "number"
            db.add(LayerField(layer_id=layer_id, field_name=key, field_alias=key,
                              field_type=field_type, field_order=order))
        rows = []
        for index, feature in enumerate(document["features"]):
            rows.append({"id": uuid5(layer_id, str(index)), "layer_id": layer_id,
                         "geom": from_shape(shape(feature["geometry"]), srid=4326),
                         "properties": properties[index], "category": properties[index].get("category"),
                         "meta": {"artifact_id": args.artifact_id, "source_srid": 4326}})
        for offset in range(0, len(rows), 500):
            await db.execute(insert(Feature), rows[offset:offset + 500])
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"data_type": "vector", "project_id": str(project_id), "layer_id": str(layer_id),
            "name": args.name, "feature_count": summary["feature_count"], "bbox": summary["bbox"], "reused": False}


def _prepare_raster(path, artifact_id):
    import rasterio
    from services.data_service.processor import RasterProcessor

    if path.stat().st_size > artifacts.MAX_ARTIFACT_BYTES:
        raise ValueError("Raster artifact exceeds the import size limit")
    with rasterio.open(path, driver="GTiff") as raster:
        if not raster.crs or raster.transform.is_identity:
            raise ValueError("GeoTIFF must include a CRS and georeferencing; plain images cannot be placed on the map")
        if raster.width * raster.height * raster.count > 100_000_000:
            raise ValueError("Raster artifact exceeds 100 million band pixels")
        bands = raster.count
    filename = f"agent_artifact_{artifact_id}.tif"
    raw = artifacts.BASE_DIR / "storage/raw" / filename
    cog = artifacts.BASE_DIR / "storage/cog" / filename
    raw.parent.mkdir(parents=True, exist_ok=True)
    cog.parent.mkdir(parents=True, exist_ok=True)
    storage = (artifacts.BASE_DIR / "storage").resolve()
    if not raw.resolve().is_relative_to(storage) or not cog.resolve().is_relative_to(storage):
        raise ValueError("Import destinations must remain inside workspace storage")
    # Only gateway-owned filenames are used; never accept a model-supplied path.
    if raw.is_symlink() or cog.is_symlink():
        raise ValueError("Import destination cannot be a symbolic link")
    if not raw.exists():
        shutil.copyfile(path, raw)
    elif hashlib.sha256(raw.read_bytes()).digest() != hashlib.sha256(path.read_bytes()).digest():
        raise ValueError("Import destination already contains different data")
    if not cog.exists():
        # The existing converter builds overviews in its input. Give it a scratch
        # copy so retries can still compare the original bytes and the source
        # artifact stays unchanged. Publish only a complete COG.
        with TemporaryDirectory(prefix=".agent-import-", dir=cog.parent) as temporary:
            scratch = Path(temporary) / "input.tif"
            converted = Path(temporary) / "output.tif"
            shutil.copyfile(raw, scratch)
            RasterProcessor.convert_to_cog(str(scratch), str(converted))
            converted.replace(cog)
    return raw, cog, bands


async def _import_raster(args, path, db):
    from services.data_service.models import RasterMetadata
    from services.data_service.db_ops import save_to_db

    bundle_id = f"agent_artifact_{args.artifact_id}"
    try:
        await _lock_import(db)
        query = select(RasterMetadata).where(RasterMetadata.bundle_id == bundle_id)
        existing = await db.scalar(query)
        reused = existing is not None
        if existing is None:
            raw, cog, bands = await asyncio.to_thread(_prepare_raster, path, args.artifact_id)
            await save_to_db(db, args.artifact_id, args.name, str(raw), cog.name, str(cog),
                             "agent_artifact", bands_count=bands, metadata_source=str(raw), bundle_id=bundle_id)
            existing = await db.scalar(query)
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return {"data_type": "raster", "id": existing.id, "index_id": existing.index_id,
            "name": existing.file_name, "reused": reused}
