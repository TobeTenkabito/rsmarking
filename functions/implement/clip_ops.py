"""
clip_ops.py — 幾何裁剪核心算法（優化版 v2）

優化重點:
  - clip_vector_by_raster : STRtree 空間索引，O(n) → O(log n + k)
  - clip_raster_by_vector : Transformer 快取，消除重複建構開銷
  - 兩階段過濾 : bbox 預篩 + 精確幾何判斷
修復重點:
  - _clean_clipped_geometry : 處理降維幾何、GeometryCollection、Sliver 碎屑
"""

import logging
from typing import Any

import rasterio
from rasterio.mask import mask as rasterio_mask
from rasterio.crs import CRS
from shapely.geometry import (
    shape, mapping,
    Polygon, MultiPolygon,
    LineString, MultiLineString,
    Point, MultiPoint,
    GeometryCollection,
)
from shapely.ops import transform as shapely_transform
from shapely.strtree import STRtree
from shapely.validation import make_valid
import pyproj

logger = logging.getLogger("functions.clip_ops")

# Sliver 面積閾值（平方單位，與輸入 CRS 一致）
# 投影座標系建議設為 1e-6（平方公尺級）；地理座標系建議 1e-10（平方度）
_DEFAULT_SLIVER_AREA_THRESHOLD = 1e-10


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
    Transformer 建構提取到迴圈外，避免重複開銷。
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


def _extract_by_dimension(geom: Any, target_dim: int) -> list[Any]:
    """
    從任意幾何體（含 GeometryCollection）中遞迴提取指定維度的子幾何。

    target_dim:
      2 → Polygon / MultiPolygon
      1 → LineString / MultiLineString
      0 → Point / MultiPoint
    """
    _DIM_TYPES = {
        2: (Polygon, MultiPolygon),
        1: (LineString, MultiLineString),
        0: (Point, MultiPoint),
    }
    target_types = _DIM_TYPES[target_dim]

    if isinstance(geom, target_types):
        # MultiXxx：拆解為子幾何列表
        if hasattr(geom, "geoms"):
            return list(geom.geoms)
        return [geom]

    if isinstance(geom, GeometryCollection):
        result = []
        for sub in geom.geoms:
            result.extend(_extract_by_dimension(sub, target_dim))
        return result

    return []


def _clean_clipped_geometry(
    clipped_geom: Any,
    original_geom: Any,
    sliver_area_threshold: float = _DEFAULT_SLIVER_AREA_THRESHOLD,
) -> Any | None:
    """
    清理 intersection 後的幾何體，處理三類拓撲污染：

    1. GeometryCollection / 降維：只保留與原始幾何同維度的子幾何
    2. Sliver 碎屑：面積低於閾值的多邊形視為無效並丟棄
    3. 空幾何：返回 None，呼叫端應跳過該 Feature

    參數
    ----
    clipped_geom          : intersection 的原始輸出
    original_geom         : 原始要素幾何體（用於判斷目標維度）
    sliver_area_threshold : 面積過濾閾值（僅對多邊形有效）

    返回
    ----
    清理後的 Shapely 幾何體，或 None（表示應丟棄該 Feature）
    """
    if clipped_geom is None or clipped_geom.is_empty:
        return None

    #  Step 1：判斷原始幾何的目標維度
    if isinstance(original_geom, (Polygon, MultiPolygon)):
        target_dim = 2
    elif isinstance(original_geom, (LineString, MultiLineString)):
        target_dim = 1
    else:
        target_dim = 0

    #  Step 2：從 intersection 結果中提取同維度子幾何
    # 若 intersection 結果本身就是目標類型，直接使用；
    # 否則從 GeometryCollection 中遞迴提取。
    _TARGET_TYPES = {
        2: (Polygon, MultiPolygon),
        1: (LineString, MultiLineString),
        0: (Point, MultiPoint),
    }
    if isinstance(clipped_geom, _TARGET_TYPES[target_dim]):
        parts = (
            list(clipped_geom.geoms)
            if hasattr(clipped_geom, "geoms")
            else [clipped_geom]
        )
    else:
        parts = _extract_by_dimension(clipped_geom, target_dim)
        if parts:
            dropped_types = {
                type(g).__name__
                for g in (
                    clipped_geom.geoms
                    if hasattr(clipped_geom, "geoms")
                    else [clipped_geom]
                )
                if not isinstance(g, _TARGET_TYPES[target_dim])
            }
            if dropped_types:
                logger.debug(
                    f"降維幾何已過濾，丟棄類型: {dropped_types}"
                )

    if not parts:
        return None

    # Step 3：Sliver 面積過濾（僅對多邊形）
    if target_dim == 2:
        before_count = len(parts)
        parts = [p for p in parts if p.area > sliver_area_threshold]
        sliver_count = before_count - len(parts)
        if sliver_count:
            logger.debug(
                f"已過濾 {sliver_count} 個 Sliver 碎屑 "
                f"(閾值={sliver_area_threshold})"
            )

    if not parts:
        return None

    # Step 4：重組為合法幾何體
    if len(parts) == 1:
        return parts[0]

    _MULTI_CONSTRUCTORS = {
        2: MultiPolygon,
        1: MultiLineString,
        0: MultiPoint,
    }
    return _MULTI_CONSTRUCTORS[target_dim](parts)


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
        fill_value = (
            nodata if nodata is not None
            else (src_nodata if src_nodata is not None else 0)
        )

        # Transformer 提取到迴圈外，只建構一次
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
    sliver_area_threshold: float = _DEFAULT_SLIVER_AREA_THRESHOLD,
) -> dict:
    """
    用柵格的空間範圍過濾/裁剪矢量要素。

    優化點
    ------
    - STRtree 空間索引：O(n) 線性掃描 → O(log n + k) 索引查詢
    - 兩階段過濾：bbox 預篩（索引層）+ 精確幾何判斷（精確層）

    修復點
    ------
    - clip 模式：_clean_clipped_geometry 處理降維幾何、GeometryCollection、Sliver

    參數
    ----
    sliver_area_threshold : clip 模式下的 Sliver 面積過濾閾值
    """
    if not geojson_features:
        raise ValueError("geojson_features 不能為空。")

    if mode not in ("intersects", "within", "clip"):
        raise ValueError(
            f"不支持的 mode: {mode}，可選值為 intersects / within / clip"
        )

    # 將裁剪框轉換到矢量 CRS
    raster_box_wgs84 = _geojson_to_shapely(clip_geometry)

    if src_vector_crs and src_vector_crs.upper() != "EPSG:4326":
        transformer = pyproj.Transformer.from_crs(
            "EPSG:4326", src_vector_crs, always_xy=True
        )
        raster_box = shapely_transform(transformer.transform, raster_box_wgs84)
    else:
        raster_box = raster_box_wgs84

    # Step 1：預解析所有幾何體，過濾掉無幾何的 feature
    indexed_features: list[tuple[int, Any]] = []
    for i, feature in enumerate(geojson_features):
        raw_geom = feature.get("geometry")
        if raw_geom:
            indexed_features.append((i, _geojson_to_shapely(raw_geom)))

    if not indexed_features:
        return _empty_feature_collection(len(geojson_features), mode)

    # Step 2：建立 STRtree 空間索引
    geom_list = [geom for _, geom in indexed_features]
    tree = STRtree(geom_list)

    # Step 3：用 bbox 快速查詢候選集，再做精確判斷
    predicate = "contains" if mode == "within" else "intersects"
    candidate_positions = tree.query(raster_box, predicate=predicate)

    result_features = []
    skipped_sliver = 0
    skipped_dimension = 0

    for pos in candidate_positions:
        orig_idx, feat_geom = indexed_features[pos]
        feature = geojson_features[orig_idx]

        if mode in ("intersects", "within"):
            result_features.append(feature)

        elif mode == "clip":
            raw_clipped = feat_geom.intersection(raster_box)

            # ✅ 修復：清理降維幾何、GeometryCollection、Sliver 碎屑
            cleaned = _clean_clipped_geometry(
                raw_clipped,
                feat_geom,
                sliver_area_threshold=sliver_area_threshold,
            )

            if cleaned is None:
                # 判斷是哪種原因被過濾，記錄統計
                if not raw_clipped.is_empty:
                    skipped_dimension += 1
                continue

            # 二次驗證：確保輸出幾何有效
            if not cleaned.is_valid:
                cleaned = make_valid(cleaned)

            result_features.append({
                **feature,
                "geometry": mapping(cleaned),
            })

    if skipped_dimension:
        logger.warning(
            f"clip 模式：{skipped_dimension} 個要素因降維或 Sliver 被過濾。"
        )

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
    """返回空的 FeatureCollection。"""
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
