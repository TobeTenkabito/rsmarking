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
from functions.implement.resampling import resample_raster
from functions.implement.atmospheric_correction import atmospheric_correction
from functions.implement.radiometric import radiometric_calibration
from functions.implement.geometric import geometric_correction
from functions.implement.dem_analysis import dem_analysis
from functions.implement.raster_transforms import raster_transform_analysis
from functions.implement.texture_features import texture_feature_analysis
from functions.implement.time_series_analysis import time_series_analysis
from functions.implement.classification import (
    supervised_classification,
    unsupervised_classification,
)
from functions.implement.segmentation import deep_learning_segmentation
from functions.implement.extraction import (
    extract_vegetation,
    extract_water,
    extract_building,
    extract_cloud,
)
from functions.implement.rasterize_ops import raster_to_vector, vector_to_raster

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
    def resample_raster(
        input_path: str,
        output_path: str,
        target_resolution_x: float,
        target_resolution_y: float | None = None,
        resolution_unit: str = "source",
        resampling_method: str = "bilinear",
    ) -> dict[str, object]:
        result = resample_raster(
            input_path,
            output_path,
            target_resolution_x,
            target_resolution_y,
            resolution_unit,
            resampling_method,
        )
        build_raster_overviews(output_path)
        return result

    @staticmethod
    def atmospheric_correction(
        input_path: str,
        output_path: str,
        method: str = "auto",
        sensor: str = "auto",
        scale_factor: float | None = None,
        offset: float | None = None,
        dark_percentile: float = 1.0,
        bright_percentile: float = 99.0,
        clamp: bool = True,
    ) -> dict[str, object]:
        result = atmospheric_correction(
            input_path=input_path,
            output_path=output_path,
            method=method,
            sensor=sensor,
            scale_factor=scale_factor,
            offset=offset,
            dark_percentile=dark_percentile,
            bright_percentile=bright_percentile,
            clamp=clamp,
        )
        build_raster_overviews(output_path)
        return result

    @staticmethod
    def radiometric_calibration(
        input_path: str,
        output_path: str,
        calibration_type: str = "auto",
        scale_factor: float | None = None,
        offset: float | None = None,
        radiance_mult: float | None = None,
        radiance_add: float | None = None,
        reflectance_mult: float | None = None,
        reflectance_add: float | None = None,
        sun_elevation: float | None = None,
        earth_sun_distance: float = 1.0,
        solar_irradiance: float | None = None,
        sun_elevation_correction: bool = True,
        clamp: bool = False,
    ) -> dict[str, object]:
        result = radiometric_calibration(
            input_path=input_path,
            output_path=output_path,
            calibration_type=calibration_type,
            scale_factor=scale_factor,
            offset=offset,
            radiance_mult=radiance_mult,
            radiance_add=radiance_add,
            reflectance_mult=reflectance_mult,
            reflectance_add=reflectance_add,
            sun_elevation=sun_elevation,
            earth_sun_distance=earth_sun_distance,
            solar_irradiance=solar_irradiance,
            sun_elevation_correction=sun_elevation_correction,
            clamp=clamp,
        )
        build_raster_overviews(output_path)
        return result

    @staticmethod
    def geometric_correction(
        input_path: str,
        output_path: str,
        dst_crs: str | None = None,
        resampling_method: str = "bilinear",
        target_resolution_x: float | None = None,
        target_resolution_y: float | None = None,
        shift_x: float = 0.0,
        shift_y: float = 0.0,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        rotation_degrees: float = 0.0,
        gcps: list[dict[str, float]] | None = None,
    ) -> dict[str, object]:
        result = geometric_correction(
            input_path=input_path,
            output_path=output_path,
            dst_crs=dst_crs,
            resampling_method=resampling_method,
            target_resolution_x=target_resolution_x,
            target_resolution_y=target_resolution_y,
            shift_x=shift_x,
            shift_y=shift_y,
            scale_x=scale_x,
            scale_y=scale_y,
            rotation_degrees=rotation_degrees,
            gcps=gcps,
        )
        build_raster_overviews(output_path)
        return result

    @staticmethod
    def dem_analysis(
        input_path: str,
        output_path: str,
        operation: str,
        band_index: int = 1,
        z_factor: float = 1.0,
        slope_unit: str = "degrees",
        hillshade_azimuth: float = 315.0,
        hillshade_altitude: float = 45.0,
        relief_window_size: int = 3,
        min_slope_degrees: float = 0.1,
    ) -> dict[str, object]:
        result = dem_analysis(
            input_path=input_path,
            output_path=output_path,
            operation=operation,
            band_index=band_index,
            z_factor=z_factor,
            slope_unit=slope_unit,
            hillshade_azimuth=hillshade_azimuth,
            hillshade_altitude=hillshade_altitude,
            relief_window_size=relief_window_size,
            min_slope_degrees=min_slope_degrees,
        )
        build_raster_overviews(output_path)
        return result

    @staticmethod
    def raster_transform_analysis(
        input_path: str,
        output_path: str,
        transform_type: str,
        band_index: int = 1,
        fourier_output: str = "magnitude",
        wavelet_output: str = "detail_energy",
        wavelet_level: int = 1,
        pca_components: int = 3,
        pca_standardize: bool = False,
    ) -> dict[str, object]:
        result = raster_transform_analysis(
            input_path=input_path,
            output_path=output_path,
            transform_type=transform_type,
            band_index=band_index,
            fourier_output=fourier_output,
            wavelet_output=wavelet_output,
            wavelet_level=wavelet_level,
            pca_components=pca_components,
            pca_standardize=pca_standardize,
        )
        build_raster_overviews(output_path)
        return result

    @staticmethod
    def texture_feature_analysis(
        input_path: str,
        output_path: str,
        texture_type: str,
        band_index: int = 1,
        gray_levels: int = 32,
        window_size: int = 7,
        glcm_distance: int = 1,
        glcm_angle: float = 0.0,
        glcm_property: str = "contrast",
        local_stat: str = "mean",
        gabor_frequency: float = 0.2,
        gabor_theta: float = 0.0,
        gabor_sigma: float = 2.0,
        lbp_radius: float = 1.0,
        lbp_points: int = 8,
    ) -> dict[str, object]:
        result = texture_feature_analysis(
            input_path=input_path,
            output_path=output_path,
            texture_type=texture_type,
            band_index=band_index,
            gray_levels=gray_levels,
            window_size=window_size,
            glcm_distance=glcm_distance,
            glcm_angle=glcm_angle,
            glcm_property=glcm_property,
            local_stat=local_stat,
            gabor_frequency=gabor_frequency,
            gabor_theta=gabor_theta,
            gabor_sigma=gabor_sigma,
            lbp_radius=lbp_radius,
            lbp_points=lbp_points,
        )
        build_raster_overviews(output_path)
        return result

    @staticmethod
    def time_series_analysis(
        input_paths: list[str],
        output_path: str,
        operation: str,
        band_index: int = 1,
        dates: list[str] | str | None = None,
        moving_window_size: int = 3,
        savgol_window_length: int = 5,
        savgol_polyorder: int = 2,
        phenology_threshold_ratio: float = 0.2,
    ) -> dict[str, object]:
        result = time_series_analysis(
            input_paths=input_paths,
            output_path=output_path,
            operation=operation,
            band_index=band_index,
            dates=dates,
            moving_window_size=moving_window_size,
            savgol_window_length=savgol_window_length,
            savgol_polyorder=savgol_polyorder,
            phenology_threshold_ratio=phenology_threshold_ratio,
        )
        build_raster_overviews(output_path)
        return result

    @staticmethod
    def supervised_classification(
        input_path: str,
        output_path: str,
        samples: list[dict[str, Any]],
        classifier: str = "nearest_centroid",
        band_indices: list[int] | None = None,
        n_estimators: int = 100,
        random_seed: int = 13,
        smoothing: int = 0,
    ) -> dict[str, object]:
        result = supervised_classification(
            input_path=input_path,
            output_path=output_path,
            samples=samples,
            classifier=classifier,
            band_indices=band_indices,
            n_estimators=n_estimators,
            random_seed=random_seed,
            smoothing=smoothing,
        )
        build_raster_overviews(output_path)
        return result

    @staticmethod
    def unsupervised_classification(
        input_path: str,
        output_path: str,
        n_classes: int = 5,
        method: str = "kmeans",
        band_indices: list[int] | None = None,
        max_samples: int = 50000,
        random_seed: int = 13,
        smoothing: int = 0,
    ) -> dict[str, object]:
        result = unsupervised_classification(
            input_path=input_path,
            output_path=output_path,
            n_classes=n_classes,
            method=method,
            band_indices=band_indices,
            max_samples=max_samples,
            random_seed=random_seed,
            smoothing=smoothing,
        )
        build_raster_overviews(output_path)
        return result

    @staticmethod
    def deep_learning_segmentation(
        input_path: str,
        output_path: str,
        model_path: str | None = None,
        backend: str = "auto",
        n_classes: int = 2,
        band_indices: list[int] | None = None,
        threshold: float = 0.5,
        random_seed: int = 13,
        max_samples: int = 50000,
        compactness: float = 0.15,
        smoothing: int = 1,
    ) -> dict[str, object]:
        result = deep_learning_segmentation(
            input_path=input_path,
            output_path=output_path,
            model_path=model_path,
            backend=backend,
            n_classes=n_classes,
            band_indices=band_indices,
            threshold=threshold,
            random_seed=random_seed,
            max_samples=max_samples,
            compactness=compactness,
            smoothing=smoothing,
        )
        build_raster_overviews(output_path)
        return result

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
        parse all variables in the expression token,return:
        {
          "A_2_3": ("A", [2, 3]),
          "B":     ("B", []),   # empty list = all bands
        }
        exclude numexpr reserved keywords.
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
        load selected bands from a file,return shape=(n_bands, H, W) text float32 text.
        indices load all bands when empty.
        """
        with rasterio.open(path) as src:
            total = src.count
            if not indices:
                bands_to_read = list(range(1, total + 1))
            else:
                for idx in indices:
                    if idx < 1 or idx > total:
                        raise ValueError(
                            f"File {path} has {total} bands; requested band index {idx} is out of range"
                        )
                bands_to_read = indices
            data = src.read(bands_to_read).astype("float32")  # (n, H, W)
        return data

    @staticmethod
    def _resolve_output_bands(token_arrays: dict[str, np.ndarray]) -> int:
        """
        validate with three priority levels and return output band count:
        1. equal dimensions -> per band
        2. single-dimension broadcast -> broadcast
        3. unequal multi-dimensional inputs -> raise an error
        """
        band_counts = [arr.shape[0] for arr in token_arrays.values()]
        unique = set(band_counts)
        if len(unique) == 1:
            return unique.pop()
        non_one = [c for c in unique if c != 1]
        if len(non_one) == 1:
            return non_one[0]
        raise ValueError(
            f"Band dimensions are incompatible and cannot be broadcast:{sorted(unique)}."
            f"Only all-equal band counts or one side with a single band are supported."
        )

    @staticmethod
    def run_raster_calculator(
        path_mapping: dict[str, str],
        expression: str,
        output_path: str
    ) -> None:
        """
        execute multi-band raster algebra.
        path_mapping: base variable name -> file path,text {"A": "a.tif", "B": "b.tif"}
        expression:   supports A,A_2,A_2_3_4 text
        output_path:  result GeoTiff path
        """
        if not path_mapping:
            raise ValueError("No input variables were provided.")
        token_map = RasterProcessor._parse_var_tokens(expression)

        # verify all base variable names are in path_mapping text
        for token, (var_name, _) in token_map.items():
            if var_name not in path_mapping:
                raise ValueError(f"Variable in expression '{var_name}' does not have a matching file path in the mapping")
        meta = None
        ref_height, ref_width = None, None
        first_path = next(iter(path_mapping.values()))
        with rasterio.open(first_path) as src:
            meta = src.meta.copy()
            ref_height, ref_width = src.height, src.width

        # verify all files share spatial dimensions
        for var_name, path in path_mapping.items():
            with rasterio.open(path) as src:
                if src.height != ref_height or src.width != ref_width:
                    raise ValueError(
                        f"text '{var_name}' spatial dimensions ({src.height}×{src.width}) "
                        f"with reference ({ref_height}×{ref_width}) do not match"
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
        clip raster with vector polygons,write result to output_path.
        clipBuilding overviews.
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
        query selected WGS84 coordinate pointmulti-band pixel values(spectrum)
        :param file_path:  COG original file path
        :param lng:        longitude (WGS84)
        :param lat:        latitude (WGS84)
        :param band_names: semantic band names,text ["Red","Green","Blue","NIR"]
        :return: {
            "bands": [{"index": 1, "name": "Band 1", "value": 0.34}, ...],
            "has_nodata": False,
            "coordinate": {"lng": 116.3, "lat": 39.9}
        }
        """
        from pyproj import Transformer

        with rasterio.open(file_path) as src:
            # 1. WGS84 -> imagery source CRS
            if src.crs and src.crs.to_epsg() != 4326:
                transformer = Transformer.from_crs(
                    "EPSG:4326", src.crs, always_xy=True
                )
                x, y = transformer.transform(lng, lat)
            else:
                x, y = lng, lat

            # 2. geographic coordinates -> pixel row and column
            row, col = src.index(x, y)

            # 3. bounds check
            if not (0 <= row < src.height and 0 <= col < src.width):
                raise ValueError(
                    f"coordinate ({lng}, {lat}) outside imagery bounds,"
                    f"imagery WGS84 bounds: {src.bounds}"
                )

            # 4. read all band values at this pixel(Window avoid reading the full image)
            window = rasterio.windows.Window(col, row, 1, 1)
            pixel_values = src.read(window=window)  # shape: (band_count, 1, 1)

            nodata = src.nodata
            result_bands = []

            for i in range(src.count):
                raw_val = pixel_values[i, 0, 0]
                is_nodata = nodata is not None and float(raw_val) == float(nodata)

                # band-name priority: input parameter > embedded file description > default numbering
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
        rasterize vector features using reference imagery.

        production considerations:
        1. automatically handle CRS conversion(WGS84 -> native imagery projection)
        2. supportsburn pixel values dynamically from attribute fields (Burn value)
        3. optimize template_meta text
        """
        if not features:
            raise ValueError("Vector feature list is empty; rasterization cannot run")

        with rasterio.open(ref_raster_path) as src:
            # 1. get reference imagery metadata
            template_meta = {
                "crs": src.crs,
                "transform": src.transform,
                "width": src.width,
                "height": src.height
            }
            dst_crs = src.crs

        # 2. coordinate reprojection (Reprojecting geometries from EPSG:4326 to target CRS)
        # vector service exports are usually 4326
        src_crs_str = "EPSG:4326"
        reprojected_features = []

        # only reproject when coordinate systems differ,reduce overhead
        need_reproject = dst_crs.to_string() != src_crs_str
        transformer = None
        if need_reproject:
            transformer = Transformer.from_crs(src_crs_str, dst_crs, always_xy=True)

        for feat in features:
            try:
                geom = shape(feat["geometry"])

                # if coordinate systems differ,perform projection conversion
                if need_reproject:
                    geom = shapely_transform(transformer.transform, geom)

                # determine burn value (priority: parameter-specified field > featurestextcategory > default value1)
                burn_val = 1
                if burn_field and burn_field in feat.get("properties", {}):
                    burn_val = feat["properties"][burn_field]
                elif "category" in feat:
                    # try to convert category map to a number,simplified here
                    burn_val = feat["category"] if isinstance(feat["category"], (int, float)) else 1

                reprojected_features.append({
                    "geometry": geom,
                    "value": burn_val
                })
            except Exception as e:
                logger.warning(f"Feature parsing or projection conversion failed; skipping: {e}")
                continue

        if not reprojected_features:
            raise ValueError("No valid geometry features are available for projection or rasterization")

        # 3. call the core algorithm to execute conversion
        # changed argument passing,adapt to reprojected geometry objects
        vector_to_raster(
            features=reprojected_features,
            template_meta=template_meta,
            out_path=output_path,
            all_touched=True
        )

        return output_path

    @staticmethod
    def run_vectorization(
        raster_path: str,
        band_index: int = 1,
        skip_nodata: bool = True,
        skip_zero: bool = True,
        max_features: int = 10000,
        simplify_tolerance: float = 0.0,
    ) -> List[Dict[str, Any]]:
        return raster_to_vector(
            raster_path=raster_path,
            band_index=band_index,
            dst_crs="EPSG:4326",
            skip_nodata=skip_nodata,
            skip_zero=skip_zero,
            max_features=max_features,
            simplify_tolerance=simplify_tolerance,
        )
