"""
change_ops.py — 变化检测核心算法

支持方法:
  - band_diff   : 单波段差值法
  - band_ratio  : 单波段比值法
  - index_diff  : 指数差值法（NDVI/NDWI/NDBI/MNDWI）
"""

import logging
from typing import Callable

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
) -> tuple[np.ndarray, dict]:
    """
    将 src_path 的所有波段重采样对齐到 ref_path 的空间格网。
    返回 (aligned_array[bands, H, W], ref_meta)
    """
    # 合并为单个上下文块，减少文件句柄开销
    with rasterio.open(ref_path) as ref, rasterio.open(src_path) as src:
        ref_meta = ref.meta.copy()
        aligned = np.zeros(
            (src.count, ref.height, ref.width),
            dtype=np.float32,
        )
        for i in range(1, src.count + 1):
            reproject(
                source=rasterio.band(src, i),
                destination=aligned[i - 1],
                dst_crs=ref.crs,
                dst_transform=ref.transform,
                dst_width=ref.width,
                dst_height=ref.height,
                resampling=Resampling.bilinear,
            )

    return aligned, ref_meta


def _read_band_as_float(path: str, band_idx: int = 1) -> np.ndarray:
    """读取指定波段并转换为 float32。"""
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


def _build_meta(base_meta: dict, dtype: str, nodata) -> dict:
    """
    基于 base_meta 构建单波段输出元数据，避免重复的 copy+update 模式。
    """
    meta = base_meta.copy()
    meta.update({"dtype": dtype, "count": 1, "driver": "GTiff", "nodata": nodata})
    return meta


def _write_raster(path: str, array: np.ndarray, meta: dict) -> None:
    """将单波段数组写入栅格文件。"""
    with rasterio.open(path, "w", **meta) as dst:
        dst.write(array, 1)


def _write_mask_if_needed(
    output_mask_path: str | None,
    diff: np.ndarray,
    threshold: float,
    threshold_mode: str,
    ref_meta: dict,
) -> int | None:
    """
    按需生成并写出二值变化掩膜，返回变化像元数（无输出路径时返回 None）。
    将 band_diff / band_ratio / index_diff 中重复的掩膜写出逻辑统一收口。
    """
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
    aligned_t2, ref_meta = _align_to_reference(path_t2, path_t1)
    band_t1 = _read_band_as_float(path_t1, band_idx)
    band_t2 = aligned_t2[band_idx - 1]

    diff = np.nan_to_num(band_t2 - band_t1, nan=0.0)

    _write_raster(output_diff_path, diff, _build_meta(ref_meta, "float32", nodata=None))
    change_pixel_count = _write_mask_if_needed(
        output_mask_path, diff, threshold, threshold_mode, ref_meta
    )

    logger.info("band_diff 完成: %s, 变化像元=%s", output_diff_path, change_pixel_count)

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

    ratio = np.nan_to_num(
        band_t2 / (band_t1 + 1e-6),
        nan=1.0, posinf=1.0, neginf=1.0,
    )

    _write_raster(output_diff_path, ratio, _build_meta(ref_meta, "float32", nodata=None))

    # 比值法：偏离 1.0 超过 threshold 视为变化，固定使用 abs 语义
    change_pixel_count = _write_mask_if_needed(
        output_mask_path,
        ratio - 1.0,        # 转换为"偏差量"，复用统一的阈值函数
        threshold,
        "abs",
        ref_meta,
    )

    logger.info("band_ratio 完成: %s, 变化像元=%s", output_diff_path, change_pixel_count)

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
    if index_type not in _INDEX_FUNCS:
        raise ValueError(f"不支持的 index_type: {index_type}")

    index_func = _INDEX_FUNCS[index_type]

    # t1 指数（以 t1_b1 为参考格网）
    b1_t1 = _read_band_as_float(path_t1_b1)
    aligned_t1_b2, ref_meta = _align_to_reference(path_t1_b2, path_t1_b1)
    idx_t1 = index_func(b1_t1, aligned_t1_b2[0])

    # t2 指数：两个波段统一对齐到 t1 格网，各调用一次 _align_to_reference
    aligned_t2_b1, _ = _align_to_reference(path_t2_b1, path_t1_b1)
    aligned_t2_b2, _ = _align_to_reference(path_t2_b2, path_t1_b1)
    idx_t2 = index_func(aligned_t2_b1[0], aligned_t2_b2[0])

    diff = np.nan_to_num(idx_t2 - idx_t1, nan=0.0)

    _write_raster(output_diff_path, diff, _build_meta(ref_meta, "float32", nodata=None))
    change_pixel_count = _write_mask_if_needed(
        output_mask_path, diff, threshold, threshold_mode, ref_meta
    )

    logger.info(
        "index_diff(%s) 完成: %s, 变化像元=%s",
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
