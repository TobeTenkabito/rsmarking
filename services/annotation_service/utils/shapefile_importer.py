import io
import zipfile
import tempfile
import os
from typing import List, Dict, Any, Tuple

import fiona
import fiona.transform
from fiona.crs import from_epsg
from shapely.geometry import shape, mapping
from shapely.ops import transform
import pyproj

from ..schemas.geojson import FeatureCreate, GeometryModel


SUPPORTED_GEOM_TYPES = {"Point", "MultiPoint", "LineString", "MultiLineString", "Polygon", "MultiPolygon"}

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
    exts = {os.path.splitext(name)[1].lower() for name in files}
    required = {".shp", ".shx", ".dbf"}
    missing = required - exts
    if missing:
        raise ValueError(f"Missing required files: {', '.join(sorted(missing))}")

    with tempfile.TemporaryDirectory() as tmpdir:
        # use the same stem,avoid fiona missing companion files
        stem = "upload"
        for name, data in files.items():
            ext = os.path.splitext(name)[1].lower()
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
            for record in src:
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
    files: Dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for name in zf.namelist():
            ext = os.path.splitext(name)[1].lower()
            if ext in {".shp", ".shx", ".dbf", ".prj", ".cpg"}:
                files[name] = zf.read(name)
    return parse_shapefile_bytes(files)
