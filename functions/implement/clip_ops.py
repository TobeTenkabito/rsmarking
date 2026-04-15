"""
clip_ops.py — 幾何裁剪核心算法（效能極致版 v3）

優化重點:
  - 徹底移除純 Python 的遞迴幾何檢查，改用 Shapely 2.0+ GEOS 向量化操作 (O(1) 迴圈開銷)
  - 批次投影轉換: PyProj 結合 shapely.transform，一次性轉換所有座標頂點
  - 批次交集運算: shapely.intersection 替代逐項計算
  - 陣列化清理: get_parts, get_type_id 結合 NumPy 遮罩，以 C 語言層級完成降維與碎屑過濾
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
        logger.warning("輸入矢量幾何體無效，已自動修復。")
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
    """向量化的幾何體清理函數，無需遞迴與 isinstance。"""
    if clipped_geom is None or shapely.is_empty(clipped_geom):
        return None

    # Step 1: 確定目標維度 (Shapely Type IDs: 0=Point, 1=Line, 3=Poly, Multi+3)
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

    # Step 2: 拍平所有 GeometryCollection 並取得子幾何體陣列與類型
    parts = shapely.get_parts(clipped_geom)
    types = shapely.get_type_id(parts)

    # 透過 NumPy 遮罩過濾降維物件
    mask = np.isin(types, target_dims)
    parts = parts[mask]

    if len(parts) == 0:
        return None

    # Step 3: Sliver 面積過濾（向量化計算所有子塊面積）
    if is_poly:
        areas = shapely.area(parts)
        parts = parts[areas > sliver_area_threshold]
        if len(parts) == 0:
            return None

    # Step 4: 幾何重建
    if len(parts) == 1:
        return parts[0]

    # 利用向量化構建函數，直接合併相同維度的陣列
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
        raise ValueError("geojson_geometries 不能為空。")

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        src_nodata = src.nodata
        fill_value = (
            nodata if nodata is not None
            else (src_nodata if src_nodata is not None else 0)
        )

        transformer = _build_transformer(src_vector_crs, raster_crs)
        shapely_geoms = [_geojson_to_shapely(g) for g in geojson_geometries]

        # 向量化批次座標轉換
        if transformer is not None:
            def transform_coords(pts):
                # 處理 2D/3D 座標陣列
                if pts.shape[1] == 3:
                    x, y, z = transformer.transform(pts[:, 0], pts[:, 1], pts[:, 2])
                    return np.column_stack((x, y, z))
                else:
                    x, y = transformer.transform(pts[:, 0], pts[:, 1])
                    return np.column_stack((x, y))

            # 將所有多邊形座標視為連續陣列，單次通過 PyProj C 擴展
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

    logger.info(f"矢量裁剪柵格完成: {output_path}")

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
        raise ValueError("geojson_features 不能為空。")

    if mode not in ("intersects", "within", "clip"):
        raise ValueError(f"不支持的 mode: {mode}")

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

    # 預處理：同時建立索引查詢用的映射與 NumPy 幾何陣列
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
    # 返回 NumPy 索引陣列
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
        # 向量化交集運算：將 C 語言執行範圍極大化
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
        logger.warning(f"clip 模式：{skipped_dimension} 個要素因降維或 Sliver 被過濾。")

    logger.info(
        f"柵格裁剪矢量完成: 輸入 {len(geojson_features)} 個要素，"
        f"輸出 {len(result_features)} 個要素 (mode={mode})"
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
