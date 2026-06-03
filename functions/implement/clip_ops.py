"""
clip_ops.py - clipping core algorithms (optimized v3)

Optimization notes:
  - Avoid recursive Python geometry checks and use Shapely 2.0+ GEOS vectorized operations.
  - Reproject coordinates in batches with PyProj and shapely.transform.
  - Use shapely.intersection instead of per-feature intersection loops.
  - Clean geometry arrays with get_parts/get_type_id and NumPy masks.
"""

import logging
from typing import Any

import numpy as np
import rasterio
from rasterio.mask import mask as rasterio_mask
from rasterio.crs import CRS
import shapely
from shapely.geometry import shape, mapping
from shapely.strtree import STRtree
import pyproj

logger = logging.getLogger("functions.clip_ops")

_DEFAULT_SLIVER_AREA_THRESHOLD = 1e-10


def _geojson_to_shapely(geojson_geom: dict) -> Any:
    geom = shape(geojson_geom)
    if not shapely.is_valid(geom):
        geom = shapely.make_valid(geom)
        logger.warning("Input vector geometry was invalid and has been repaired automatically.")
    return geom


def _build_transformer(
    src_crs_str: str,
    dst_crs: CRS,
) -> pyproj.Transformer | None:
    src_crs_str = src_crs_str or "EPSG:4326"
    dst_crs_str = dst_crs.to_string()

    if CRS.from_user_input(src_crs_str) == dst_crs:
        return None

    return pyproj.Transformer.from_crs(
        src_crs_str, dst_crs_str, always_xy=True
    )


def _clean_clipped_geometry(
    clipped_geom: Any,
    original_geom: Any,
    sliver_area_threshold: float = _DEFAULT_SLIVER_AREA_THRESHOLD,
) -> Any | None:
    """Clean clipped geometry without recursive isinstance checks."""
    if clipped_geom is None or shapely.is_empty(clipped_geom):
        return None

    # Step 1: determine target dimensions (Shapely type IDs: 0=Point, 1=Line, 3=Poly, Multi+3)
    orig_type = shapely.get_type_id(original_geom)
    if orig_type in (3, 6):
        target_dims = (3, 6)
        is_poly = True
    elif orig_type in (1, 5):
        target_dims = (1, 5)
        is_poly = False
    else:
        target_dims = (0, 4)
        is_poly = False

    # Step 2: flatten GeometryCollection parts
    parts = shapely.get_parts(clipped_geom)
    types = shapely.get_type_id(parts)

    # Filter dimension changes with a NumPy mask.
    mask = np.isin(types, target_dims)
    parts = parts[mask]

    if len(parts) == 0:
        return None

    # Step 3: filter polygon slivers.
    if is_poly:
        areas = shapely.area(parts)
        parts = parts[areas > sliver_area_threshold]
        if len(parts) == 0:
            return None

    # Step 4: rebuild geometry.
    if len(parts) == 1:
        return parts[0]

    # Merge arrays of the same geometry dimension.
    if is_poly:
        return shapely.multipolygons(parts)
    elif orig_type in (1, 5):
        return shapely.multilinestrings(parts)
    else:
        return shapely.multipoints(parts)


def clip_raster_by_vector(
    raster_path: str,
    output_path: str,
    geojson_geometries: list[dict],
    src_vector_crs: str = "EPSG:4326",
    crop: bool = True,
    nodata: float | None = None,
    all_touched: bool = False,
) -> dict:
    if not geojson_geometries:
        raise ValueError("geojson_geometries cannot be empty.")

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        src_nodata = src.nodata
        fill_value = (
            nodata if nodata is not None
            else (src_nodata if src_nodata is not None else 0)
        )

        transformer = _build_transformer(src_vector_crs, raster_crs)
        shapely_geoms = [_geojson_to_shapely(g) for g in geojson_geometries]

        # Reproject vector geometries to the raster CRS when needed.
        if transformer is not None:
            def transform_coords(pts):
                # Handle 2D and 3D coordinate arrays.
                if pts.shape[1] == 3:
                    x, y, z = transformer.transform(pts[:, 0], pts[:, 1], pts[:, 2])
                    return np.column_stack((x, y, z))
                else:
                    x, y = transformer.transform(pts[:, 0], pts[:, 1])
                    return np.column_stack((x, y))

            # Transform all coordinates in a single vectorized PyProj pass.
            shapely_geoms = shapely.transform(shapely_geoms, transform_coords)

        reprojected_geoms = [mapping(g) for g in shapely_geoms]

        clipped_data, clipped_transform = rasterio_mask(
            src,
            reprojected_geoms,
            crop=crop,
            nodata=fill_value,
            all_touched=all_touched,
            filled=True,
        )

        out_meta = src.meta.copy()
        out_meta.update({
            "driver": "GTiff",
            "height": clipped_data.shape[1],
            "width": clipped_data.shape[2],
            "transform": clipped_transform,
            "nodata": fill_value,
        })

        with rasterio.open(output_path, "w", **out_meta) as dest:
            dest.write(clipped_data)

    logger.info(f"Vector-to-raster clipping complete: {output_path}")

    return {
        "width": clipped_data.shape[2],
        "height": clipped_data.shape[1],
        "bands": clipped_data.shape[0],
        "nodata": fill_value,
        "output_path": output_path,
    }


def clip_vector_by_raster(
    clip_geometry: dict,
    geojson_features: list[dict],
    src_vector_crs: str = "EPSG:4326",
    mode: str = "intersects",
    sliver_area_threshold: float = _DEFAULT_SLIVER_AREA_THRESHOLD,
) -> dict:
    if not geojson_features:
        raise ValueError("geojson_features cannot be empty.")

    if mode not in ("intersects", "within", "clip"):
        raise ValueError(f"Unsupported mode: {mode}")

    raster_box_wgs84 = _geojson_to_shapely(clip_geometry)

    if src_vector_crs and src_vector_crs.upper() != "EPSG:4326":
        transformer = pyproj.Transformer.from_crs(
            "EPSG:4326", src_vector_crs, always_xy=True
        )
        def transform_box(pts):
            x, y = transformer.transform(pts[:, 0], pts[:, 1])
            return np.column_stack((x, y))
        raster_box = shapely.transform(raster_box_wgs84, transform_box)
    else:
        raster_box = raster_box_wgs84

    # Preprocess features into an index map and geometry array.
    indexed_features = []
    geoms_list = []
    for i, feature in enumerate(geojson_features):
        raw_geom = feature.get("geometry")
        if raw_geom:
            geom = _geojson_to_shapely(raw_geom)
            indexed_features.append((i, geom))
            geoms_list.append(geom)

    if not geoms_list:
        return _empty_feature_collection(len(geojson_features), mode)

    geom_array = np.array(geoms_list)
    tree = STRtree(geom_array)

    predicate = "contains" if mode == "within" else "intersects"
    # STRtree returns NumPy indices.
    candidate_indices = tree.query(raster_box, predicate=predicate)

    if len(candidate_indices) == 0:
        return _empty_feature_collection(len(geojson_features), mode)

    result_features = []
    skipped_dimension = 0

    if mode in ("intersects", "within"):
        for idx in candidate_indices:
            orig_idx = indexed_features[idx][0]
            result_features.append(geojson_features[orig_idx])

    elif mode == "clip":
        # Vectorized intersection keeps the work inside GEOS.
        candidate_geoms = geom_array[candidate_indices]
        clipped_geoms = shapely.intersection(candidate_geoms, raster_box)

        for i, idx in enumerate(candidate_indices):
            orig_idx = indexed_features[idx][0]
            feature = geojson_features[orig_idx]

            cleaned = _clean_clipped_geometry(
                clipped_geoms[i],
                candidate_geoms[i],
                sliver_area_threshold=sliver_area_threshold,
            )

            if cleaned is None:
                if not shapely.is_empty(clipped_geoms[i]):
                    skipped_dimension += 1
                continue

            if not shapely.is_valid(cleaned):
                cleaned = shapely.make_valid(cleaned)

            result_features.append({
                **feature,
                "geometry": mapping(cleaned),
            })

    if skipped_dimension:
        logger.warning(
            f"clip mode: {skipped_dimension} features were dropped due to dimension collapse or slivers."
        )

    logger.info(
        f"Raster-to-vector clipping complete: input {len(geojson_features)} features, "
        f"output {len(result_features)} features (mode={mode})"
    )

    return {
        "type": "FeatureCollection",
        "features": result_features,
        "meta": {
            "input_count": len(geojson_features),
            "output_count": len(result_features),
            "mode": mode,
            "skipped_sliver_or_dimension": skipped_dimension,
        },
    }


def _empty_feature_collection(input_count: int, mode: str) -> dict:
    return {
        "type": "FeatureCollection",
        "features": [],
        "meta": {
            "input_count": input_count,
            "output_count": 0,
            "mode": mode,
            "skipped_sliver_or_dimension": 0,
        },
    }
