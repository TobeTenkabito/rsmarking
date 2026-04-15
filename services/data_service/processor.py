import os
import logging
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
    def run_raster_calculator(path_mapping: dict[str, str], expression: str, output_path: str) -> None:
        """
        执行自定义栅格代数运算
        :param path_mapping: 变量名到文件路径的映射，如 {"A": "path_to_a.tif", "B": "path_to_b.tif"}
        :param expression: 数学表达式，如 "(A - B) / (A + B)"
        :param output_path: 结果保存路径
        """
        if not path_mapping:
            raise ValueError("No input variables provided.")
        arrays_dict = {}
        meta = None
        height, width = None, None
        for var_name, path in path_mapping.items():
            with rasterio.open(path) as src:
                if meta is None:
                    meta = src.meta.copy()
                    meta.update({"dtype": "float32", "count": 1, "driver": "GTiff"})
                    height, width = src.height, src.width
                elif src.height != height or src.width != width:
                    raise ValueError(f"波段 {var_name} 的维度与其他波段不一致！")
                arrays_dict[var_name] = src.read(1).astype("float32")
        try:
            with np.errstate(divide="ignore", invalid="ignore"):
                result = ne.evaluate(expression, local_dict=arrays_dict)
            result = np.nan_to_num(result, nan=0.0, posinf=1.0, neginf=-1.0)

        except Exception as e:
            raise ValueError(f"表达式解析或计算失败: {str(e)}")
        with rasterio.open(output_path, "w", **meta) as dest:
            dest.write(result, 1)

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
            paths, output_path, RasterProcessor._ExtractionRegistry.get("cloud"), min_bands=1, **kwargs,)

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
