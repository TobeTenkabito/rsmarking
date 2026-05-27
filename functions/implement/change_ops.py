import logging
from typing import Callable, Sequence

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

logger = logging.getLogger("functions.change_ops")


_INDEX_FUNCS: dict[str, Callable[[np.ndarray, np.ndarray], np.ndarray]] = {
    "ndvi": lambda b1, b2: (b2 - b1) / (b2 + b1 + 1e-6),
    "ndwi": lambda b1, b2: (b1 - b2) / (b1 + b2 + 1e-6),
    "ndbi": lambda b1, b2: (b1 - b2) / (b1 + b2 + 1e-6),
    "mndwi": lambda b1, b2: (b1 - b2) / (b1 + b2 + 1e-6),
}


def _align_to_reference(
    src_path: str,
    ref_path: str,
    band_indexes: Sequence[int] | None = None,
) -> tuple[np.ndarray, dict]:
    """Read selected source bands on the reference raster grid."""
    with rasterio.open(ref_path) as ref, rasterio.open(src_path) as src:
        ref_meta = ref.meta.copy()
        if band_indexes is None:
            band_indexes = tuple(range(1, src.count + 1))
        else:
            band_indexes = tuple(band_indexes)

        invalid = [idx for idx in band_indexes if idx < 1 or idx > src.count]
        if invalid:
            raise ValueError(
                f"Band index out of range for {src_path}: {invalid}; "
                f"file has {src.count} band(s)"
            )

        same_grid = (
            src.crs == ref.crs
            and src.transform == ref.transform
            and src.width == ref.width
            and src.height == ref.height
        )
        if same_grid:
            return src.read(list(band_indexes), out_dtype="float32"), ref_meta

        aligned = np.empty((len(band_indexes), ref.height, ref.width), dtype=np.float32)
        for out_idx, band_idx in enumerate(band_indexes):
            reproject(
                source=rasterio.band(src, band_idx),
                destination=aligned[out_idx],
                dst_crs=ref.crs,
                dst_transform=ref.transform,
                dst_width=ref.width,
                dst_height=ref.height,
                resampling=Resampling.bilinear,
            )

    return aligned, ref_meta


def _read_band_as_float(path: str, band_idx: int = 1) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(band_idx, out_dtype="float32")


def _normalize_to_uint8(arr: np.ndarray) -> np.ndarray:
    min_val, max_val = np.nanmin(arr), np.nanmax(arr)
    if max_val == min_val:
        return np.zeros_like(arr, dtype=np.uint8)

    normalized = np.empty_like(arr, dtype=np.float32)
    np.subtract(arr, min_val, out=normalized)
    np.multiply(normalized, 255.0 / (max_val - min_val), out=normalized)
    np.nan_to_num(normalized, copy=False, nan=0.0, posinf=255.0, neginf=0.0)
    return normalized.astype(np.uint8)


def _apply_threshold(
    diff_arr: np.ndarray,
    threshold: float,
    mode: str = "abs",
) -> np.ndarray:
    if mode == "abs":
        return (np.abs(diff_arr) > threshold).astype(np.uint8)
    if mode == "positive":
        return (diff_arr > threshold).astype(np.uint8)
    if mode == "negative":
        return (diff_arr < -threshold).astype(np.uint8)
    raise ValueError(f"Unsupported threshold mode: {mode}")


def _build_meta(base_meta: dict, dtype: str, nodata) -> dict:
    meta = base_meta.copy()
    meta.update({"dtype": dtype, "count": 1, "driver": "GTiff", "nodata": nodata})
    return meta


def _write_raster(path: str, array: np.ndarray, meta: dict) -> None:
    with rasterio.open(path, "w", **meta) as dst:
        dst.write(array, 1)


def _write_mask_if_needed(
    output_mask_path: str | None,
    diff: np.ndarray,
    threshold: float,
    threshold_mode: str,
    ref_meta: dict,
) -> int | None:
    if output_mask_path is None:
        return None

    mask = _apply_threshold(diff, threshold, threshold_mode)
    _write_raster(output_mask_path, mask, _build_meta(ref_meta, "uint8", nodata=0))
    return int(mask.sum())


def band_diff(
    path_t1: str,
    path_t2: str,
    output_diff_path: str,
    output_mask_path: str | None = None,
    band_idx: int = 1,
    threshold: float = 0.1,
    threshold_mode: str = "abs",
) -> dict:
    aligned_t2, ref_meta = _align_to_reference(path_t2, path_t1, band_indexes=[band_idx])
    band_t1 = _read_band_as_float(path_t1, band_idx)
    band_t2 = aligned_t2[0]

    diff = np.empty_like(band_t2, dtype=np.float32)
    np.subtract(band_t2, band_t1, out=diff)
    np.nan_to_num(diff, copy=False, nan=0.0)

    _write_raster(output_diff_path, diff, _build_meta(ref_meta, "float32", nodata=None))
    change_pixel_count = _write_mask_if_needed(
        output_mask_path, diff, threshold, threshold_mode, ref_meta
    )

    logger.info("band_diff complete: %s, changed_pixels=%s", output_diff_path, change_pixel_count)

    return {
        "method": "band_diff",
        "diff_path": output_diff_path,
        "mask_path": output_mask_path,
        "change_pixel_count": change_pixel_count,
        "threshold": threshold,
    }


def band_ratio(
    path_t1: str,
    path_t2: str,
    output_diff_path: str,
    output_mask_path: str | None = None,
    band_idx: int = 1,
    threshold: float = 0.2,
) -> dict:
    aligned_t2, ref_meta = _align_to_reference(path_t2, path_t1, band_indexes=[band_idx])
    band_t1 = _read_band_as_float(path_t1, band_idx)
    band_t2 = aligned_t2[0]

    denominator = band_t1 + 1e-6
    ratio = np.empty_like(band_t2, dtype=np.float32)
    with np.errstate(divide="ignore", invalid="ignore"):
        np.divide(band_t2, denominator, out=ratio)
    np.nan_to_num(ratio, copy=False, nan=1.0, posinf=1.0, neginf=1.0)

    _write_raster(output_diff_path, ratio, _build_meta(ref_meta, "float32", nodata=None))
    change_pixel_count = _write_mask_if_needed(
        output_mask_path,
        ratio - 1.0,
        threshold,
        "abs",
        ref_meta,
    )

    logger.info("band_ratio complete: %s, changed_pixels=%s", output_diff_path, change_pixel_count)

    return {
        "method": "band_ratio",
        "diff_path": output_diff_path,
        "mask_path": output_mask_path,
        "change_pixel_count": change_pixel_count,
        "threshold": threshold,
    }


def index_diff(
    path_t1_b1: str,
    path_t1_b2: str,
    path_t2_b1: str,
    path_t2_b2: str,
    output_diff_path: str,
    output_mask_path: str | None = None,
    index_type: str = "ndvi",
    threshold: float = 0.15,
    threshold_mode: str = "abs",
) -> dict:
    if index_type not in _INDEX_FUNCS:
        raise ValueError(f"Unsupported index_type: {index_type}")

    index_func = _INDEX_FUNCS[index_type]

    b1_t1 = _read_band_as_float(path_t1_b1)
    aligned_t1_b2, ref_meta = _align_to_reference(path_t1_b2, path_t1_b1, band_indexes=[1])
    idx_t1 = index_func(b1_t1, aligned_t1_b2[0])

    aligned_t2_b1, _ = _align_to_reference(path_t2_b1, path_t1_b1, band_indexes=[1])
    aligned_t2_b2, _ = _align_to_reference(path_t2_b2, path_t1_b1, band_indexes=[1])
    idx_t2 = index_func(aligned_t2_b1[0], aligned_t2_b2[0])

    diff = np.empty_like(idx_t2, dtype=np.float32)
    np.subtract(idx_t2, idx_t1, out=diff)
    np.nan_to_num(diff, copy=False, nan=0.0)

    _write_raster(output_diff_path, diff, _build_meta(ref_meta, "float32", nodata=None))
    change_pixel_count = _write_mask_if_needed(
        output_mask_path, diff, threshold, threshold_mode, ref_meta
    )

    logger.info(
        "index_diff(%s) complete: %s, changed_pixels=%s",
        index_type, output_diff_path, change_pixel_count,
    )

    return {
        "method": f"index_diff_{index_type}",
        "diff_path": output_diff_path,
        "mask_path": output_mask_path,
        "change_pixel_count": change_pixel_count,
        "threshold": threshold,
        "index_type": index_type,
    }
