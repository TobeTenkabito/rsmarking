"""
clip_ops.py — 几何裁剪核心算法

支持两种模式:
  - clip_raster_by_vector : 用矢量多边形裁剪栅格 (rasterio.mask)
  - clip_vector_by_raster : 用栅格空间范围裁剪矢量要素 (返回 GeoJSON FeatureCollection)
"""

import logging
from typing import Any


import rasterio
from rasterio.mask import mask as rasterio_mask
from rasterio.warp import transform_bounds
from rasterio.crs import CRS
from shapely.geometry import shape, mapping, box
from shapely.ops import transform as shapely_transform
from shapely.validation import make_valid
import pyproj

logger = logging.getLogger("functions.clip_ops")


def _geojson_to_shapely(geojson_geom: dict) -> Any:
    """
    将 GeoJSON geometry dict 转为 Shapely 几何体，
    并自动修复无效拓扑。
    """
    geom = shape(geojson_geom)
    if not geom.is_valid:
        geom = make_valid(geom)
        logger.warning("输入矢量几何体无效，已自动修复。")
    return geom


def _reproject_shapely_to_raster_crs(
    shapely_geom: Any,
    src_crs_str: str,
    dst_crs: CRS,
) -> Any:
    """
    将 Shapely 几何体从 src_crs 重投影到 dst_crs。
    src_crs_str: EPSG 字符串，如 "EPSG:4326"
    """
    src_crs_str = src_crs_str or "EPSG:4326"
    dst_crs_str = dst_crs.to_string()

    # 如果 CRS 相同则跳过
    if CRS.from_user_input(src_crs_str) == dst_crs:
        return shapely_geom

    transformer = pyproj.Transformer.from_crs(
        src_crs_str, dst_crs_str, always_xy=True
    )
    reprojected = shapely_transform(transformer.transform, shapely_geom)
    return reprojected


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
    用一个或多个矢量多边形裁剪栅格影像。

    参数
    ----
    raster_path       : 输入栅格路径 (COG/GeoTIFF)
    output_path       : 输出裁剪结果路径
    geojson_geometries: GeoJSON geometry 对象列表 (type: Polygon / MultiPolygon)
    src_vector_crs    : 矢量几何体的坐标系，默认 EPSG:4326
    crop              : True = 裁剪到掩膜最小外接矩形；False = 保持原始范围
    nodata            : 掩膜区域外的填充值，None 则继承原栅格 nodata
    all_touched       : True = 边界像元也纳入掩膜

    返回
    ----
    dict: 裁剪结果的基本元数据
    """
    if not geojson_geometries:
        raise ValueError("geojson_geometries 不能为空。")

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        src_nodata = src.nodata
        fill_value = nodata if nodata is not None else (src_nodata if src_nodata is not None else 0)

        # 将所有矢量几何体重投影到栅格 CRS
        reprojected_geoms = []
        for geojson_geom in geojson_geometries:
            shapely_geom = _geojson_to_shapely(geojson_geom)
            reprojected = _reproject_shapely_to_raster_crs(
                shapely_geom, src_vector_crs, raster_crs
            )
            reprojected_geoms.append(mapping(reprojected))

        # 执行掩膜裁剪
        clipped_data, clipped_transform = rasterio_mask(
            src,
            reprojected_geoms,
            crop=crop,
            nodata=fill_value,
            all_touched=all_touched,
            filled=True,
        )

        # 构建输出元数据
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

    logger.info(f"矢量裁剪栅格完成: {output_path}")

    return {
        "width": clipped_data.shape[2],
        "height": clipped_data.shape[1],
        "bands": clipped_data.shape[0],
        "nodata": fill_value,
        "output_path": output_path,
    }


def clip_vector_by_raster(
    raster_path: str,
    geojson_features: list[dict],
    src_vector_crs: str = "EPSG:4326",
    mode: str = "intersects",
) -> dict:
    """
    用栅格的空间范围过滤/裁剪矢量要素。

    参数
    ----
    raster_path      : 输入栅格路径，用于读取空间范围
    geojson_features : GeoJSON Feature 对象列表（含 geometry + properties）
    src_vector_crs   : 矢量要素的坐标系，默认 EPSG:4326
    mode             : 空间关系模式
                       - "intersects" : 保留与栅格范围相交的要素（默认）
                       - "within"     : 仅保留完全在栅格范围内的要素
                       - "clip"       : 裁剪几何体到栅格范围边界

    返回
    ----
    dict: GeoJSON FeatureCollection，包含过滤/裁剪后的要素
    """
    if not geojson_features:
        raise ValueError("geojson_features 不能为空。")

    if mode not in ("intersects", "within", "clip"):
        raise ValueError(f"不支持的 mode: {mode}，可选值为 intersects / within / clip")

    with rasterio.open(raster_path) as src:
        raster_crs = src.crs
        # 将栅格 bounds 转换为 WGS84（矢量通常为 4326）
        bounds_wgs84 = transform_bounds(raster_crs, "EPSG:4326", *src.bounds)

    raster_box_wgs84 = box(*bounds_wgs84)  # Shapely Polygon

    # 如果矢量不是 4326，需要将 raster_box 转换到矢量 CRS
    if src_vector_crs and src_vector_crs.upper() != "EPSG:4326":
        transformer = pyproj.Transformer.from_crs(
            "EPSG:4326", src_vector_crs, always_xy=True
        )
        raster_box = shapely_transform(transformer.transform, raster_box_wgs84)
    else:
        raster_box = raster_box_wgs84

    result_features = []

    for feature in geojson_features:
        raw_geom = feature.get("geometry")
        if not raw_geom:
            continue

        feat_geom = _geojson_to_shapely(raw_geom)

        if mode == "intersects":
            if feat_geom.intersects(raster_box):
                result_features.append(feature)

        elif mode == "within":
            if feat_geom.within(raster_box):
                result_features.append(feature)

        elif mode == "clip":
            if feat_geom.intersects(raster_box):
                clipped_geom = feat_geom.intersection(raster_box)
                if not clipped_geom.is_empty:
                    clipped_feature = {
                        **feature,
                        "geometry": mapping(clipped_geom),
                    }
                    result_features.append(clipped_feature)

    logger.info(
        f"栅格裁剪矢量完成: 输入 {len(geojson_features)} 个要素，"
        f"输出 {len(result_features)} 个要素 (mode={mode})"
    )

    return {
        "type": "FeatureCollection",
        "features": result_features,
        "meta": {
            "input_count": len(geojson_features),
            "output_count": len(result_features),
            "mode": mode,
            "raster_bounds_wgs84": list(bounds_wgs84),
        },
    }