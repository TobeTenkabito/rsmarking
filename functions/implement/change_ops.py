"""
change_ops.py — 变化检测核心算法

支持方法:
  - band_diff   : 单波段差值法
  - band_ratio  : 单波段比值法
  - index_diff  : 指数差值法（NDVI/NDWI/NDBI/MNDWI）
"""

import logging
import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject, calculate_default_transform

logger = logging.getLogger("functions.change_ops")


def _align_to_reference(
    src_path: str,
    ref_path: str,
) -> tuple[np.ndarray, dict]:
    """
    将 src_path 的所有波段重采样对齐到 ref_path 的空间格网。
    返回 (aligned_array[bands, H, W], ref_meta)
    """
    with rasterio.open(ref_path) as ref:
        ref_meta = ref.meta.copy()
        ref_crs = ref.crs
        ref_transform = ref.transform
        ref_height = ref.height
        ref_width = ref.width

    with rasterio.open(src_path) as src:
        band_count = src.count
        aligned = np.zeros(
            (band_count, ref_height, ref_width),
            dtype=np.float32,
        )
        for i in range(1, band_count + 1):
            reproject(
                source=rasterio.band(src, i),
                destination=aligned[i - 1],
                dst_crs=ref_crs,
                dst_transform=ref_transform,
                dst_width=ref_width,
                dst_height=ref_height,
                resampling=Resampling.bilinear,
            )

    return aligned, ref_meta


def _read_band_as_float(path: str, band_idx: int = 1) -> np.ndarray:
    with rasterio.open(path) as src:
        return src.read(band_idx).astype(np.float32)


def _normalize_to_uint8(arr: np.ndarray) -> np.ndarray:
    """将任意范围的浮点数组归一化到 0-255 uint8，用于可视化输出。"""
    min_val, max_val = np.nanmin(arr), np.nanmax(arr)
    if max_val == min_val:
        return np.zeros_like(arr, dtype=np.uint8)
    normalized = (arr - min_val) / (max_val - min_val) * 255
    return normalized.astype(np.uint8)


def _apply_threshold(
    diff_arr: np.ndarray,
    threshold: float,
    mode: str = "abs",
) -> np.ndarray:
    """
    将差值图二值化为变化掩膜。

    mode:
      "abs"      : |diff| > threshold 视为变化
      "positive" : diff > threshold（仅正向变化，如植被增加）
      "negative" : diff < -threshold（仅负向变化，如植被减少）
    """
    if mode == "abs":
        return (np.abs(diff_arr) > threshold).astype(np.uint8)
    elif mode == "positive":
        return (diff_arr > threshold).astype(np.uint8)
    elif mode == "negative":
        return (diff_arr < -threshold).astype(np.uint8)
    else:
        raise ValueError(f"不支持的 threshold mode: {mode}")


def band_diff(
    path_t1: str,
    path_t2: str,
    output_diff_path: str,
    output_mask_path: str | None = None,
    band_idx: int = 1,
    threshold: float = 0.1,
    threshold_mode: str = "abs",
) -> dict:
    """
    单波段差值法变化检测。
    diff = t2 - t1

    参数
    ----
    path_t1/t2       : 两期栅格路径（t1=早期，t2=晚期）
    output_diff_path : 差值图输出路径（float32）
    output_mask_path : 二值变化掩膜输出路径（uint8），None 则不输出
    band_idx         : 使用的波段索引（1-based）
    threshold        : 变化判定阈值
    threshold_mode   : abs / positive / negative
    """
    # 对齐到 t1 格网
    aligned_t2, ref_meta = _align_to_reference(path_t2, path_t1)
    band_t1 = _read_band_as_float(path_t1, band_idx)
    band_t2 = aligned_t2[band_idx - 1]

    diff = band_t2 - band_t1
    diff = np.nan_to_num(diff, nan=0.0)

    # 写出差值图
    diff_meta = ref_meta.copy()
    diff_meta.update({"dtype": "float32", "count": 1, "driver": "GTiff", "nodata": None})
    with rasterio.open(output_diff_path, "w", **diff_meta) as dst:
        dst.write(diff, 1)

    change_pixel_count = None

    # 写出二值掩膜（可选）
    if output_mask_path:
        mask = _apply_threshold(diff, threshold, threshold_mode)
        change_pixel_count = int(mask.sum())
        mask_meta = ref_meta.copy()
        mask_meta.update({"dtype": "uint8", "count": 1, "driver": "GTiff", "nodata": 0})
        with rasterio.open(output_mask_path, "w", **mask_meta) as dst:
            dst.write(mask, 1)

    logger.info(f"band_diff 完成: {output_diff_path}, 变化像元={change_pixel_count}")

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
    """
    单波段比值法变化检测。
    ratio = t2 / (t1 + ε)，偏离 1.0 越远表示变化越大。
    """
    aligned_t2, ref_meta = _align_to_reference(path_t2, path_t1)
    band_t1 = _read_band_as_float(path_t1, band_idx)
    band_t2 = aligned_t2[band_idx - 1]

    ratio = band_t2 / (band_t1 + 1e-6)
    ratio = np.nan_to_num(ratio, nan=1.0, posinf=1.0, neginf=1.0)

    diff_meta = ref_meta.copy()
    diff_meta.update({"dtype": "float32", "count": 1, "driver": "GTiff", "nodata": None})
    with rasterio.open(output_diff_path, "w", **diff_meta) as dst:
        dst.write(ratio, 1)

    change_pixel_count = None
    if output_mask_path:
        # 偏离 1.0 超过 threshold 视为变化
        mask = (np.abs(ratio - 1.0) > threshold).astype(np.uint8)
        change_pixel_count = int(mask.sum())
        mask_meta = ref_meta.copy()
        mask_meta.update({"dtype": "uint8", "count": 1, "driver": "GTiff", "nodata": 0})
        with rasterio.open(output_mask_path, "w", **mask_meta) as dst:
            dst.write(mask, 1)

    logger.info(f"band_ratio 完成: {output_diff_path}, 变化像元={change_pixel_count}")

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
    """
    指数差值法变化检测。
    diff = Index(t2) - Index(t1)

    index_type: ndvi / ndwi / ndbi / mndwi
    各指数波段约定（均为 1-based band 1）:
      ndvi  : b1=Red,   b2=NIR
      ndwi  : b1=Green, b2=NIR
      ndbi  : b1=SWIR,  b2=NIR
      mndwi : b1=Green, b2=SWIR
    """
    _INDEX_FUNCS = {
        "ndvi":  lambda b1, b2: (b2 - b1) / (b2 + b1 + 1e-6),
        "ndwi":  lambda b1, b2: (b1 - b2) / (b1 + b2 + 1e-6),
        "ndbi":  lambda b1, b2: (b1 - b2) / (b1 + b2 + 1e-6),
        "mndwi": lambda b1, b2: (b1 - b2) / (b1 + b2 + 1e-6),
    }
    if index_type not in _INDEX_FUNCS:
        raise ValueError(f"不支持的 index_type: {index_type}")

    index_func = _INDEX_FUNCS[index_type]

    # t1 指数
    b1_t1 = _read_band_as_float(path_t1_b1)
    aligned_t1_b2, ref_meta = _align_to_reference(path_t1_b2, path_t1_b1)
    b2_t1 = aligned_t1_b2[0]
    idx_t1 = index_func(b1_t1, b2_t1)

    # t2 指数（对齐到 t1 格网）
    aligned_t2_b1, _ = _align_to_reference(path_t2_b1, path_t1_b1)
    aligned_t2_b2, _ = _align_to_reference(path_t2_b2, path_t1_b1)
    idx_t2 = index_func(aligned_t2_b1[0], aligned_t2_b2[0])

    diff = idx_t2 - idx_t1
    diff = np.nan_to_num(diff, nan=0.0)

    diff_meta = ref_meta.copy()
    diff_meta.update({"dtype": "float32", "count": 1, "driver": "GTiff", "nodata": None})
    with rasterio.open(output_diff_path, "w", **diff_meta) as dst:
        dst.write(diff, 1)

    change_pixel_count = None
    if output_mask_path:
        mask = _apply_threshold(diff, threshold, threshold_mode)
        change_pixel_count = int(mask.sum())
        mask_meta = ref_meta.copy()
        mask_meta.update({"dtype": "uint8", "count": 1, "driver": "GTiff", "nodata": 0})
        with rasterio.open(output_mask_path, "w", **mask_meta) as dst:
            dst.write(mask, 1)

    logger.info(f"index_diff({index_type}) 完成: {output_diff_path}, 变化像元={change_pixel_count}")

    return {
        "method": f"index_diff_{index_type}",
        "diff_path": output_diff_path,
        "mask_path": output_mask_path,
        "change_pixel_count": change_pixel_count,
        "threshold": threshold,
        "index_type": index_type,
    }
