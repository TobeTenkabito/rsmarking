"""
clip_ops.py — 幾何裁剪核心算法（優化版）

優化重點:
  - clip_vector_by_raster : STRtree 空間索引，O(n) → O(log n + k)
  - clip_raster_by_vector : Transformer 快取，消除重複建構開銷
  - 兩階段過濾 : bbox 預篩 + 精確幾何判斷
"""

import logging
from typing import Any

import rasterio
from rasterio.mask import mask as rasterio_mask
from rasterio.crs import CRS
from shapely.geometry import shape, mapping
from shapely.ops import transform as shapely_transform
from shapely.strtree import STRtree          # ← 新增
from shapely.validation import make_valid
import pyproj

logger = logging.getLogger("functions.clip_ops")


def _geojson_to_shapely(geojson_geom: dict) -> Any:
    """將 GeoJSON geometry dict 轉為 Shapely 幾何體，並自動修復無效拓撲。"""
    geom = shape(geojson_geom)
    if not geom.is_valid:
        geom = make_valid(geom)
        logger.warning("輸入矢量幾何體無效，已自動修復。")
    return geom


def _build_transformer(
    src_crs_str: str,
    dst_crs: CRS,
) -> pyproj.Transformer | None:
    """
    建立 pyproj.Transformer；若兩個 CRS 相同則返回 None（無需轉換）。
    【優化】將 Transformer 建構提取到迴圈外，避免重複開銷。
    """
    src_crs_str = src_crs_str or "EPSG:4326"
    dst_crs_str = dst_crs.to_string()

    if CRS.from_user_input(src_crs_str) == dst_crs:
        return None

    return pyproj.Transformer.from_crs(
        src_crs_str, dst_crs_str, always_xy=True
    )


def _reproject_shapely(
    shapely_geom: Any,
    transformer: pyproj.Transformer | None,
) -> Any:
    """使用預建的 Transformer 做重投影；transformer 為 None 時直接返回原幾何體。"""
    if transformer is None:
        return shapely_geom
    return shapely_transform(transformer.transform, shapely_geom)



def clip_raster_by_vector(
    raster_path: str,
    output_path: str,
    geojson_geometries: list[dict],
    src_vector_crs: str = "EPSG:4326",
    crop: bool = True,
    nodata: float | None = None,
    all_touched: bool = False,
) -> dict:
    """
    用一個或多個矢量多邊形裁剪柵格影像。

    優化點
    ------
    - Transformer 只建構一次，不在迴圈內重複建立。
    """
    if not geojson_geometries:
        raise ValueError("geojson_geometries 不能為空。")

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        src_nodata = src.nodata
        fill_value = nodata if nodata is not None else (src_nodata if src_nodata is not None else 0)

        # ✅ 優化：Transformer 提取到迴圈外，只建構一次
        transformer = _build_transformer(src_vector_crs, raster_crs)

        reprojected_geoms = []
        for geojson_geom in geojson_geometries:
            shapely_geom = _geojson_to_shapely(geojson_geom)
            reprojected = _reproject_shapely(shapely_geom, transformer)
            reprojected_geoms.append(mapping(reprojected))

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
) -> dict:
    """
    用柵格的空間範圍過濾/裁剪矢量要素。

    優化點
    ------
    - STRtree 空間索引：O(n) 線性掃描 → O(log n + k) 索引查詢
    - 兩階段過濾：bbox 預篩（索引層）+ 精確幾何判斷（精確層）
    - 跳過無幾何體的 feature，避免無效計算
    """
    if not geojson_features:
        raise ValueError("geojson_features 不能為空。")

    if mode not in ("intersects", "within", "clip"):
        raise ValueError(f"不支持的 mode: {mode}，可選值為 intersects / within / clip")

    # 將裁剪框轉換到矢量 CRS
    raster_box_wgs84 = _geojson_to_shapely(clip_geometry)

    if src_vector_crs and src_vector_crs.upper() != "EPSG:4326":
        transformer = pyproj.Transformer.from_crs(
            "EPSG:4326", src_vector_crs, always_xy=True
        )
        raster_box = shapely_transform(transformer.transform, raster_box_wgs84)
    else:
        raster_box = raster_box_wgs84

    # ✅ 優化 Step 1：預解析所有幾何體，過濾掉無幾何的 feature
    indexed_features: list[tuple[int, Any]] = []   # (原始索引, shapely_geom)
    for i, feature in enumerate(geojson_features):
        raw_geom = feature.get("geometry")
        if raw_geom:
            indexed_features.append((i, _geojson_to_shapely(raw_geom)))

    if not indexed_features:
        return _empty_feature_collection(len(geojson_features), mode)

    # ✅ 優化 Step 2：建立 STRtree 空間索引
    geom_list = [geom for _, geom in indexed_features]
    tree = STRtree(geom_list)

    # ✅ 優化 Step 3：用 bbox 快速查詢候選集，再做精確判斷
    #   tree.query() 返回的是 geom_list 中的位置索引
    if mode == "intersects":
        candidate_positions = tree.query(raster_box, predicate="intersects")
    elif mode == "within":
        candidate_positions = tree.query(raster_box, predicate="contains")  # A contains B ↔ B within A
    else:  # clip
        candidate_positions = tree.query(raster_box, predicate="intersects")

    result_features = []

    for pos in candidate_positions:
        orig_idx, feat_geom = indexed_features[pos]
        feature = geojson_features[orig_idx]

        if mode in ("intersects", "within"):
            # STRtree predicate 已完成精確過濾，直接收錄
            result_features.append(feature)

        elif mode == "clip":
            clipped_geom = feat_geom.intersection(raster_box)
            if not clipped_geom.is_empty:
                result_features.append({
                    **feature,
                    "geometry": mapping(clipped_geom),
                })

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
        },
    }


def _empty_feature_collection(input_count: int, mode: str) -> dict:
    """返回空的 FeatureCollection。"""
    return {
        "type": "FeatureCollection",
        "features": [],
        "meta": {
            "input_count": input_count,
            "output_count": 0,
            "mode": mode,
        },
    }