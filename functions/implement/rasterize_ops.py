import math
from typing import Any, Dict, Generator, List, Tuple

import numpy as np
import rasterio
from pyproj import CRS, Transformer
from rasterio.features import rasterize, shapes
from shapely.geometry import mapping, shape
from shapely.geometry.base import BaseGeometry
from shapely.ops import transform as shapely_transform, unary_union


def vector_to_raster(
        features: List[Dict[str, Any]],
        template_meta: Dict[str, Any],
        out_path: str,
        all_touched: bool = False,
        dtype: str = rasterio.uint8,
        nodata: int = 0
) -> str:
    """
    将矢量要素转换为栅格文件 (TIFF)

    工业级优化：
    1. 支持生成器惰性求值，防止千万级矢量导致 OOM
    2. 兼容 Shapely 对象与 GeoJSON 字典
    3. 支持动态烧录值读取
    """

    # 1. 使用生成器 (Generator) 替代列表推导式
    # 空间复杂度从 O(N) 降低至 O(1)
    def shape_generator() -> Generator[Tuple[BaseGeometry, int], None, None]:
        for f in features:
            geom = f['geometry']

            # 兼容性兜底：如果在外部没有被转化为 shapely 对象，则在此转换
            if not isinstance(geom, BaseGeometry):
                from shapely.geometry import shape
                geom = shape(geom)

            # 读取外部计算好的烧录值 (burn value)，如果不存在则默认 1
            val = f.get('value', 1)
            yield (geom, val)

    # 2. 创建输出掩码阵列 (C底层实现，速度极快)
    out_arr = rasterize(
        shapes=shape_generator(),
        out_shape=(template_meta['height'], template_meta['width']),
        transform=template_meta['transform'],
        fill=nodata,
        all_touched=all_touched,
        dtype=dtype
    )

    # 3. 写入文件
    with rasterio.open(
            out_path,
            'w',
            driver='GTiff',
            height=template_meta['height'],
            width=template_meta['width'],
            count=1,
            dtype=dtype,
            crs=template_meta['crs'],
            transform=template_meta['transform'],
            nodata=nodata,
            compress='lzw',
            predictor=2  # 对整型栅格数据有极大压缩增益的预测器
    ) as dst:
        dst.write(out_arr, 1)

    return out_path


def _json_safe_value(value: Any) -> int | float | str:
    if isinstance(value, np.generic):
        value = value.item()

    if isinstance(value, float):
        if not math.isfinite(value):
            return str(value)
        if value.is_integer():
            return int(value)
        return value

    if isinstance(value, (int, str)):
        return value

    return float(value)


def _clean_polygon_geometry(geom: BaseGeometry) -> BaseGeometry | None:
    if geom.is_empty:
        return None

    if not geom.is_valid:
        geom = geom.buffer(0)

    if geom.is_empty:
        return None

    if geom.geom_type in {"Polygon", "MultiPolygon"}:
        return geom

    if geom.geom_type == "GeometryCollection":
        polygons = [
            part
            for part in geom.geoms
            if part.geom_type in {"Polygon", "MultiPolygon"} and not part.is_empty
        ]
        if not polygons:
            return None
        geom = unary_union(polygons)
        if geom.geom_type in {"Polygon", "MultiPolygon"} and not geom.is_empty:
            return geom

    return None


def raster_to_vector(
    raster_path: str,
    band_index: int = 1,
    dst_crs: str = "EPSG:4326",
    skip_nodata: bool = True,
    skip_zero: bool = True,
    max_features: int = 10000,
    simplify_tolerance: float = 0.0,
) -> List[Dict[str, Any]]:
    """
    Polygonize one raster band into GeoJSON features.

    The function is intentionally tuned for mask/classification rasters:
    NoData pixels are skipped by default, and zero-valued pixels are skipped
    by default so extraction masks produce foreground polygons only.
    """
    if band_index < 1:
        raise ValueError("band_index must be >= 1")
    if max_features < 1:
        raise ValueError("max_features must be >= 1")

    features: List[Dict[str, Any]] = []

    with rasterio.open(raster_path) as src:
        if band_index > src.count:
            raise ValueError(
                f"Band index {band_index} is out of range for raster with {src.count} band(s)"
            )

        data = src.read(band_index)
        if data.dtype.name not in {"int16", "int32", "uint8", "uint16", "float32"}:
            data = data.astype("float32")
        include_mask = np.ones(data.shape, dtype=bool)

        if np.issubdtype(data.dtype, np.floating):
            include_mask &= np.isfinite(data)

        if skip_nodata and src.nodata is not None:
            nodata = src.nodata
            if isinstance(nodata, float) and math.isnan(nodata):
                include_mask &= ~np.isnan(data)
            else:
                include_mask &= data != nodata

        if skip_zero:
            include_mask &= data != 0

        transformer = None
        source_crs = src.crs
        if dst_crs and not source_crs:
            raise ValueError("Raster CRS is required for vectorization into EPSG:4326")
        if source_crs and dst_crs:
            source = CRS.from_user_input(source_crs)
            target = CRS.from_user_input(dst_crs)
            if not source.equals(target):
                transformer = Transformer.from_crs(source, target, always_xy=True)

        for geom_json, value in shapes(data, mask=include_mask, transform=src.transform):
            geom = _clean_polygon_geometry(shape(geom_json))
            if geom is None:
                continue

            if simplify_tolerance > 0:
                geom = geom.simplify(simplify_tolerance, preserve_topology=True)
                geom = _clean_polygon_geometry(geom)
                if geom is None:
                    continue

            if transformer is not None:
                geom = shapely_transform(transformer.transform, geom)
                geom = _clean_polygon_geometry(geom)
                if geom is None:
                    continue

            raster_value = _json_safe_value(value)
            if len(features) >= max_features:
                raise ValueError(
                    f"Raster vectorization exceeded max_features={max_features}. "
                    "Use a classified/mask raster or raise the limit."
                )
            features.append({
                "type": "Feature",
                "geometry": mapping(geom),
                "properties": {
                    "raster_value": raster_value,
                    "band_index": band_index,
                    "category": f"value_{raster_value}",
                },
            })

    return features
