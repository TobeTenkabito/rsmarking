import os
import logging
import re
import numpy as np
import numexpr as ne
import rasterio
from typing import TypedDict, TypeAlias, ParamSpec, List, Dict, Any
from collections.abc import Callable
from pyproj import Transformer
from shapely.geometry import shape
from shapely.ops import transform as shapely_transform

from functions.implement.clip_ops import (
    clip_raster_by_vector,
    clip_vector_by_raster,
)
from functions.implement.spatial_ops import (
    get_wgs84_bounds,
    compute_center_from_bounds,
)
from functions.implement.spectral_indices import (
    calculate_ndvi_array,
    calculate_ndwi_array,
    calculate_ndbi_array,
    calculate_mndwi_array,
)
from functions.implement.io_ops import (
    build_raster_overviews,
    convert_raster_to_cog,
)
from functions.implement.manipulation import (
    extract_raster_bands,
    merge_raster_bands,
)
from functions.implement.extraction import (
    extract_vegetation,
    extract_water,
    extract_building,
    extract_cloud,
)
from functions.implement.rasterize_ops import vector_to_raster

logger = logging.getLogger("data_service.processor")

BandArray: TypeAlias = np.ndarray
BandList: TypeAlias = list[BandArray]
MaskArray: TypeAlias = np.ndarray

P = ParamSpec("P")


class MetadataDict(TypedDict):
    file_name: str
    crs: str
    bounds: list[float]
    bounds_wgs84: list[float]
    center: tuple[float, float]
    width: int
    height: int
    bands: int
    data_type: str
    resolution: tuple[float, float]


class RasterProcessor:
    @staticmethod
    def extract_metadata(file_path: str) -> MetadataDict:
        with rasterio.open(file_path) as src:
            crs_str: str = src.crs.to_string() if src.crs else "EPSG:4326"

            bounds_wgs84 = get_wgs84_bounds(src.crs, src.bounds)
            center = compute_center_from_bounds(bounds_wgs84)

            return {
                "file_name": os.path.basename(file_path),
                "crs": crs_str,
                "bounds": list(src.bounds),
                "bounds_wgs84": list(bounds_wgs84),
                "center": center,
                "width": src.width,
                "height": src.height,
                "bands": src.count,
                "data_type": src.dtypes[0],
                "resolution": src.res,
            }

    @staticmethod
    def extract_bands(input_path: str, output_path: str, band_indices: list[int],) -> None:
        extract_raster_bands(input_path, output_path, band_indices)
        build_raster_overviews(output_path)

    @staticmethod
    def merge_bands(input_paths: list[str], output_path: str,) -> None:
        merge_raster_bands(input_paths, output_path)
        build_raster_overviews(output_path)

    @staticmethod
    def convert_to_cog(input_path: str, output_path: str,) -> None:
        convert_raster_to_cog(input_path, output_path)

    @staticmethod
    def _run_two_band_index(
        band1_path: str,
        band2_path: str,
        output_path: str,
        index_func: Callable[[BandArray, BandArray], BandArray],
    ) -> None:

        with rasterio.open(band1_path) as src1, rasterio.open(band2_path) as src2:
            meta = src1.meta.copy()
            meta.update({"dtype": "float32", "count": 1, "driver": "GTiff"})
            band1: BandArray = src1.read(1)
            band2: BandArray = src2.read(
                1, out_shape=(src1.height, src1.width)
            )
            result: BandArray = index_func(band1, band2)
            with rasterio.open(output_path, "w", **meta) as dest:
                dest.write(result, 1)
        build_raster_overviews(output_path)

    @staticmethod
    def _parse_var_tokens(expression: str) -> dict[str, tuple[str, list[int]]]:
        """
        解析表达式中所有变量 token，返回：
        {
          "A_2_3": ("A", [2, 3]),
          "B":     ("B", []),   # 空列表 = 全波段
        }
        排除 numexpr 保留关键字。
        """
        RESERVED = {
            'sin','cos','tan','arcsin','arccos','arctan','arctan2',
            'sinh','cosh','tanh','exp','log','log10','sqrt','abs',
            'where','pi','e','expm1','log1p','real','imag','conj',
            'complex'
        }
        pattern = re.compile(r'\b([A-Za-z][A-Za-z0-9]*)(?:_(\d+(?:_\d+)*))?(?=\s*[^(]|$)')
        tokens = {}
        for m in re.finditer(r'\b([A-Za-z][A-Za-z0-9]*(?:_\d+)*)\b', expression):
            token = m.group(1)
            parts = token.split('_')
            split_pos = len(parts)
            for i, p in enumerate(parts):
                if p.isdigit():
                    split_pos = i
                    break
            var_name = '_'.join(parts[:split_pos])
            indices = [int(p) for p in parts[split_pos:]]
            if var_name.lower() in RESERVED:
                continue
            if not var_name:
                continue
            tokens[token] = (var_name, indices)
        return tokens

    @staticmethod
    def _load_bands(path: str, indices: list[int]) -> np.ndarray:
        """
        从文件加载指定波段，返回 shape=(n_bands, H, W) 的 float32 数组。
        indices 为空时加载全部波段。
        """
        with rasterio.open(path) as src:
            total = src.count
            if not indices:
                bands_to_read = list(range(1, total + 1))
            else:
                for idx in indices:
                    if idx < 1 or idx > total:
                        raise ValueError(
                            f"文件 {path} 共 {total} 个波段，请求的波段索引 {idx} 越界"
                        )
                bands_to_read = indices
            data = src.read(bands_to_read).astype("float32")  # (n, H, W)
        return data

    @staticmethod
    def _resolve_output_bands(token_arrays: dict[str, np.ndarray]) -> int:
        """
        按三级优先级校验并返回输出波段数：
        1. 维度对等 → 逐波段
        2. 单位维广播 → 广播
        3. 多维不等 → 报错
        """
        band_counts = [arr.shape[0] for arr in token_arrays.values()]
        unique = set(band_counts)
        if len(unique) == 1:
            return unique.pop()
        non_one = [c for c in unique if c != 1]
        if len(non_one) == 1:
            return non_one[0]
        raise ValueError(
            f"波段维度不兼容，无法广播：{sorted(unique)}。"
            f"仅支持「全部相等」或「一方为1波段」两种情况。"
        )

    @staticmethod
    def run_raster_calculator(
        path_mapping: dict[str, str],
        expression: str,
        output_path: str
    ) -> None:
        """
        执行多波段栅格代数运算。
        path_mapping: 基础变量名 -> 文件路径，如 {"A": "a.tif", "B": "b.tif"}
        expression:   支持 A、A_2、A_2_3_4 三种变量形式
        output_path:  结果 GeoTiff 路径
        """
        if not path_mapping:
            raise ValueError("未提供输入变量。")
        token_map = RasterProcessor._parse_var_tokens(expression)

        # 校验所有基础变量名都在 path_mapping 中
        for token, (var_name, _) in token_map.items():
            if var_name not in path_mapping:
                raise ValueError(f"表达式中的变量 '{var_name}' 未在映射中提供对应文件路径")
        meta = None
        ref_height, ref_width = None, None
        first_path = next(iter(path_mapping.values()))
        with rasterio.open(first_path) as src:
            meta = src.meta.copy()
            ref_height, ref_width = src.height, src.width

        # 校验所有文件空间维度一致
        for var_name, path in path_mapping.items():
            with rasterio.open(path) as src:
                if src.height != ref_height or src.width != ref_width:
                    raise ValueError(
                        f"变量 '{var_name}' 的空间维度 ({src.height}×{src.width}) "
                        f"与基准 ({ref_height}×{ref_width}) 不一致"
                    )
        token_arrays: dict[str, np.ndarray] = {}
        for token, (var_name, indices) in token_map.items():
            token_arrays[token] = RasterProcessor._load_bands(
                path_mapping[var_name], indices
            )
        output_bands = RasterProcessor._resolve_output_bands(token_arrays)
        results = []
        with np.errstate(divide="ignore", invalid="ignore"):
            for band_idx in range(output_bands):
                local_dict = {}
                for token, arr in token_arrays.items():
                    if arr.shape[0] == 1:
                        local_dict[token] = arr[0]
                    else:
                        local_dict[token] = arr[band_idx]

                safe_expr = expression
                safe_dict = {}
                for token in local_dict:
                    safe_name = f"_v{abs(hash(token)) % 100000}"
                    safe_expr = re.sub(rf'\b{re.escape(token)}\b', safe_name, safe_expr)
                    safe_dict[safe_name] = local_dict[token]

                band_result = ne.evaluate(safe_expr, local_dict=safe_dict)
                band_result = np.nan_to_num(
                    band_result.astype("float32"),
                    nan=0.0, posinf=1.0, neginf=-1.0
                )
                results.append(band_result)

        output_array = np.stack(results, axis=0)

        meta.update({
            "dtype": "float32",
            "count": output_bands,
            "driver": "GTiff"
        })
        with rasterio.open(output_path, "w", **meta) as dest:
            dest.write(output_array)

        build_raster_overviews(output_path)

    @staticmethod
    def calculate_ndvi(red_path: str, nir_path: str, output_path: str,) -> None:
        RasterProcessor._run_two_band_index(
            red_path, nir_path, output_path, calculate_ndvi_array,)

    @staticmethod
    def calculate_ndwi(green_path: str, nir_path: str, output_path: str,) -> None:
        RasterProcessor._run_two_band_index(
            green_path, nir_path, output_path, calculate_ndwi_array,)

    @staticmethod
    def calculate_ndbi(swir_path: str, nir_path: str, output_path: str,) -> None:
        RasterProcessor._run_two_band_index(
            swir_path, nir_path, output_path, calculate_ndbi_array,)

    @staticmethod
    def calculate_mndwi(green_path: str, swir_path: str, output_path: str,) -> None:
        RasterProcessor._run_two_band_index(
            green_path, swir_path, output_path, calculate_mndwi_array,)

    class _ExtractionRegistry:
        _registry: dict[str, Callable] = {
            "vegetation": extract_vegetation,
            "water": extract_water,
            "building": extract_building,
            "cloud": extract_cloud,
        }

        @classmethod
        def get(cls, name: str) -> Callable:
            if name not in cls._registry:
                raise ValueError(f"Unknown typing: {name}")
            return cls._registry[name]

    @staticmethod
    def _run_extraction_task(
        paths: list[str],
        output_path: str,
        extraction_func: Callable,
        min_bands: int,
        **kwargs,
    ) -> None:

        if len(paths) < min_bands:
            raise ValueError(f"Task needs  {min_bands} bands at least!")
        bands: BandList = []
        with rasterio.open(paths[0]) as first_src:
            meta = first_src.meta.copy()
            meta.update({"dtype": "uint8", "count": 1, "driver": "GTiff"})
            height: int = first_src.height
            width: int = first_src.width
            for path in paths:
                with rasterio.open(path) as src:
                    if src.height != height or src.width != width:
                        raise ValueError("Bands are not consistency!")
                    bands.append(src.read(1))
        mask: MaskArray = extraction_func(bands, **kwargs)
        with rasterio.open(output_path, "w", **meta) as dest:
            dest.write(mask.astype("uint8"), 1)
        build_raster_overviews(output_path)

    @staticmethod
    def run_vegetation_extraction(paths: list[str], output_path: str, **kwargs,) -> None:
        RasterProcessor._run_extraction_task(
            paths, output_path, RasterProcessor._ExtractionRegistry.get("vegetation"), min_bands=2, **kwargs,)

    @staticmethod
    def run_water_extraction(paths: list[str], output_path: str, **kwargs,) -> None:
        RasterProcessor._run_extraction_task(
            paths, output_path, RasterProcessor._ExtractionRegistry.get("water"), min_bands=2, **kwargs,)

    @staticmethod
    def run_building_extraction(paths: list[str], output_path: str, **kwargs,) -> None:
        RasterProcessor._run_extraction_task(
            paths, output_path, RasterProcessor._ExtractionRegistry.get("building"), min_bands=2, **kwargs,)

    @staticmethod
    def run_cloud_extraction(paths: list[str], output_path: str, **kwargs,) -> None:
        RasterProcessor._run_extraction_task(
            paths, output_path, RasterProcessor._ExtractionRegistry.get("cloud"), min_bands=2, **kwargs,)

    @staticmethod
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
        用矢量多边形裁剪栅格，结果写入 output_path。
        裁剪完成后自动构建金字塔。
        """
        result = clip_raster_by_vector(
            raster_path=raster_path,
            output_path=output_path,
            geojson_geometries=geojson_geometries,
            src_vector_crs=src_vector_crs,
            crop=crop,
            nodata=nodata,
            all_touched=all_touched,
        )
        build_raster_overviews(output_path)
        return result

    @staticmethod
    def query_spectrum(
            file_path: str,
            lng: float,
            lat: float,
            band_names: list[str] | None = None,
    ) -> dict:
        """
        查詢指定 WGS84 坐標點的多波段像素值（光譜）
        :param file_path:  COG 或原始文件路徑
        :param lng:        經度 (WGS84)
        :param lat:        緯度 (WGS84)
        :param band_names: 波段語義名稱，如 ["Red","Green","Blue","NIR"]
        :return: {
            "bands": [{"index": 1, "name": "Band 1", "value": 0.34}, ...],
            "has_nodata": False,
            "coordinate": {"lng": 116.3, "lat": 39.9}
        }
        """
        from pyproj import Transformer

        with rasterio.open(file_path) as src:
            # 1. WGS84 → 影像原始 CRS
            if src.crs and src.crs.to_epsg() != 4326:
                transformer = Transformer.from_crs(
                    "EPSG:4326", src.crs, always_xy=True
                )
                x, y = transformer.transform(lng, lat)
            else:
                x, y = lng, lat

            # 2. 地理坐標 → 像素行列號
            row, col = src.index(x, y)

            # 3. 邊界檢查
            if not (0 <= row < src.height and 0 <= col < src.width):
                raise ValueError(
                    f"坐標 ({lng}, {lat}) 超出影像範圍，"
                    f"影像 WGS84 範圍: {src.bounds}"
                )

            # 4. 讀取所有波段在該像素的值（Window 避免讀整張影像）
            window = rasterio.windows.Window(col, row, 1, 1)
            pixel_values = src.read(window=window)  # shape: (band_count, 1, 1)

            nodata = src.nodata
            result_bands = []

            for i in range(src.count):
                raw_val = pixel_values[i, 0, 0]
                is_nodata = nodata is not None and float(raw_val) == float(nodata)

                # 波段名稱優先級: 傳入參數 > 文件內嵌描述 > 默認編號
                if band_names and i < len(band_names):
                    name = band_names[i]
                elif src.descriptions[i]:
                    name = src.descriptions[i]
                else:
                    name = f"Band {i + 1}"

                result_bands.append({
                    "index": i + 1,
                    "name": name,
                    "value": None if is_nodata else float(raw_val),
                })

            return {
                "bands": result_bands,
                "has_nodata": any(b["value"] is None for b in result_bands),
                "coordinate": {"lng": lng, "lat": lat},
            }

    @staticmethod
    def run_rasterization(
            features: List[Dict[str, Any]],
            ref_raster_path: str,
            output_path: str,
            burn_field: str = None
    ) -> str:
        """
        基于参考影像将矢量要素栅格化。

        工业级考量：
        1. 自动处理 CRS 转换（WGS84 -> 影像原生投影）
        2. 支持根据属性字段动态烧录像素值 (Burn value)
        3. 优化 template_meta 获取逻辑
        """
        if not features:
            raise ValueError("矢量要素列表为空，无法执行栅格化")

        with rasterio.open(ref_raster_path) as src:
            # 1. 获取参考影像元数据
            template_meta = {
                "crs": src.crs,
                "transform": src.transform,
                "width": src.width,
                "height": src.height
            }
            dst_crs = src.crs

        # 2. 坐标重投影 (Reprojecting geometries from EPSG:4326 to target CRS)
        # 矢量服务导出的通常是 4326
        src_crs_str = "EPSG:4326"
        reprojected_features = []

        # 只有在坐标系不一致时才执行重投影，减少开销
        need_reproject = dst_crs.to_string() != src_crs_str
        transformer = None
        if need_reproject:
            transformer = Transformer.from_crs(src_crs_str, dst_crs, always_xy=True)

        for feat in features:
            try:
                geom = shape(feat["geometry"])

                # 如果坐标系不一致，执行投影转换
                if need_reproject:
                    geom = shapely_transform(transformer.transform, geom)

                # 确定烧录值 (优先级: 参数指定字段 > features中的category > 默认值1)
                burn_val = 1
                if burn_field and burn_field in feat.get("properties", {}):
                    burn_val = feat["properties"][burn_field]
                elif "category" in feat:
                    # 尝试将 category 映射为数字，这里简化处理
                    burn_val = feat["category"] if isinstance(feat["category"], (int, float)) else 1

                reprojected_features.append({
                    "geometry": geom,
                    "value": burn_val
                })
            except Exception as e:
                logger.warning(f"要素解析或投影转换失败，跳过: {e}")
                continue

        if not reprojected_features:
            raise ValueError("没有有效的几何要素可供投影或栅格化")

        # 3. 调用核心算法执行转换
        # 修改了参数传递方式，适配重投影后的几何体对象
        vector_to_raster(
            features=reprojected_features,
            template_meta=template_meta,
            out_path=output_path,
            all_touched=True
        )

        return output_path
