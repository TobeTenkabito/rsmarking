import io
import zipfile
import tempfile
import os
from pathlib import PurePosixPath
from typing import List, Dict, Any, Tuple

import fiona
import fiona.transform
from fiona.crs import from_epsg
from shapely.geometry import shape, mapping
from shapely.ops import transform
import pyproj

from ..schemas.geojson import FeatureCreate, GeometryModel


SUPPORTED_GEOM_TYPES = {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}
SHAPEFILE_EXTENSIONS = {".shp", ".shx", ".dbf", ".prj", ".cpg"}
MAX_SHAPEFILE_BYTES = 64 * 1024 * 1024
MAX_SHAPEFILE_FEATURES = 100_000
MAX_ZIP_MEMBERS = 100


class ShapefileLimitError(ValueError):
    """The import exceeds a bounded resource limit."""


def _validated_components(names) -> dict[str, str]:
    if len(names) > len(SHAPEFILE_EXTENSIONS):
        raise ValueError("Upload exactly one Shapefile dataset (at most five components)")
    extensions = {}
    stems = set()
    for name in names:
        normalized = str(name or "").replace("\\", "/")
        path = PurePosixPath(normalized)
        if not normalized or path.is_absolute() or ".." in path.parts or ":" in normalized or "\x00" in normalized:
            raise ValueError("Invalid Shapefile component name")
        ext = path.suffix.lower()
        if ext not in SHAPEFILE_EXTENSIONS:
            raise ValueError("Unsupported Shapefile component; allowed: .shp, .shx, .dbf, .prj, .cpg")
        if ext in extensions.values():
            raise ValueError("Duplicate Shapefile component extension")
        extensions[name] = ext
        stems.add(str(path.with_suffix("")).casefold())
    if len(stems) != 1:
        raise ValueError("All Shapefile components must belong to the same dataset")
    missing = {".shp", ".shx", ".dbf"} - set(extensions.values())
    if missing:
        raise ValueError(f"Missing required files: {', '.join(sorted(missing))}")
    return extensions


async def read_shapefile_uploads(uploads) -> dict[str, bytes]:
    """Bound reads before materializing multipart files in application memory."""
    _validated_components([upload.filename for upload in uploads])
    files = {}
    total = 0
    for upload in uploads:
        data = bytearray()
        while True:
            chunk = await upload.read(min(1024 * 1024, MAX_SHAPEFILE_BYTES - total + 1))
            if not chunk:
                break
            total += len(chunk)
            if total > MAX_SHAPEFILE_BYTES:
                raise ShapefileLimitError("Shapefile components exceed the 64 MiB import limit")
            data.extend(chunk)
        files[upload.filename] = bytes(data)
    return files

FIONA_TYPE_MAP: Dict[str, str] = {
    "str" : "string",
    "int" : "number",
    "float": "number",
    "date": "string",
}


def _reproject_geometry(geom_dict: dict, src_crs: str) -> dict:
    """
    text fiona text geometry dict reproject to EPSG:4326.
    src_crs text fiona text CRS text(text 'EPSG:32651').
    """
    if src_crs is None:
        # no .prj,default to 4326
        return geom_dict

    src = pyproj.CRS(src_crs)
    dst = pyproj.CRS("EPSG:4326")

    if src == dst:
        return geom_dict

    project = pyproj.Transformer.from_crs(src, dst, always_xy=True).transform
    geom = shape(geom_dict)
    reprojected = transform(project, geom)
    return mapping(reprojected)


def _infer_field_type(fiona_type: str) -> str:
    """text fiona schema field typefield type"""
    return FIONA_TYPE_MAP.get(fiona_type.lower(), "string")


def parse_shapefile_bytes(
    files: Dict[str, bytes]
) -> Tuple[List[FeatureCreate], List[Dict[str, Any]]]:
    """
    parse Shapefile text.

    parameters:
        files: { "filename.shp": bytes, "filename.dbf": bytes, ... }

    return:
        (features: List[FeatureCreate], fields: List[dict])
        fields format: [{ "field_name": str, "field_type": str, "field_alias": str }]

    exception:
        ValueError: Missing required files / unsupported geometry type
    """
    extensions = _validated_components(list(files))
    if sum(len(data) for data in files.values()) > MAX_SHAPEFILE_BYTES:
        raise ShapefileLimitError("Shapefile components exceed the 64 MiB import limit")

    with tempfile.TemporaryDirectory() as tmpdir:
        # use the same stem,avoid fiona missing companion files
        stem = "upload"
        for name, data in files.items():
            ext = extensions[name]
            dest = os.path.join(tmpdir, stem + ext)
            with open(dest, "wb") as f:
                f.write(data)

        shp_path = os.path.join(tmpdir, stem + ".shp")

        with fiona.open(shp_path, encoding="utf-8") as src:
            src_crs = src.crs_wkt or src.crs.get("init") if src.crs else None

            # parsefield definitions
            raw_schema = src.schema.get("properties", {})
            fields = [
                {
                    "field_name": fname,
                    "field_type": _infer_field_type(ftype),
                    "field_alias": fname,
                }
                for fname, ftype in raw_schema.items()
            ]

            # parsefeatures
            features: List[FeatureCreate] = []
            for position, record in enumerate(src):
                if position >= MAX_SHAPEFILE_FEATURES:
                    raise ShapefileLimitError("Shapefile exceeds the 100,000 feature import limit")
                geom_dict = record.get("geometry")
                if geom_dict is None:
                    continue  # skip empty geometry

                geom_type = geom_dict.get("type", "")
                if geom_type not in SUPPORTED_GEOM_TYPES:
                    continue

                # reproject to 4326
                geom_4326 = _reproject_geometry(geom_dict, src_crs)

                props = dict(record.get("properties") or {})
                # text date text JSON convert to string
                props = {k: str(v) if v is not None and not isinstance(v, (int, float, bool, str)) else v
                         for k, v in props.items()}

                fc = FeatureCreate(
                    geometry=GeometryModel(**geom_4326),
                    properties=props,
                    category=props.get("category", "default"),
                    srid=4326,
                )
                features.append(fc)

    return features, fields


def parse_shapefile_zip(zip_bytes: bytes) -> Tuple[List[FeatureCreate], List[Dict[str, Any]]]:
    """
    supports .zip upload,automatically unpack and call parse_shapefile_bytes.
    """
    if len(zip_bytes) > MAX_SHAPEFILE_BYTES:
        raise ShapefileLimitError("ZIP exceeds the 64 MiB import limit")
    files: Dict[str, bytes] = {}
    try:
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            members = zf.infolist()
            if len(members) > MAX_ZIP_MEMBERS:
                raise ShapefileLimitError("ZIP contains too many members")
            components = [info for info in members if not info.is_dir() and PurePosixPath(info.filename).suffix.lower() in SHAPEFILE_EXTENSIONS]
            _validated_components([info.filename for info in components])
            if sum(info.file_size for info in components) > MAX_SHAPEFILE_BYTES:
                raise ShapefileLimitError("Decompressed Shapefile exceeds the 64 MiB import limit")
            total = 0
            for info in components:
                with zf.open(info) as source:
                    data = source.read(MAX_SHAPEFILE_BYTES - total + 1)
                total += len(data)
                if total > MAX_SHAPEFILE_BYTES:
                    raise ShapefileLimitError("Decompressed Shapefile exceeds the 64 MiB import limit")
                files[info.filename] = data
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise ValueError("Invalid or encrypted Shapefile ZIP") from exc
    return parse_shapefile_bytes(files)
