import numpy as np
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class JRCParams:
    mndwi_threshold: float = 0.0
    ndvi_max: float = 0.1
    nir_max: float = 0.15
    deep_nir_max: float = 0.05
    deep_swir_max: float = 0.05
    auto_threshold: bool = False
    return_probability: bool = False


def _normalize(arr: np.ndarray, name: str = "Band") -> np.ndarray:
    arr = arr.astype(float)
    orig_max = np.nanmax(arr)
    orig_min = np.nanmin(arr)
    
    print(f"[数据检查] {name} - 原始最大值: {orig_max:.4f}, 原始最小值: {orig_min:.4f}")
    if orig_max > 10:
        arr = arr / 10000.0
        print(f"  --> {name} 检测到大数值，已自动缩放 10000 倍")
    
    return arr


def _safe_div(a, b, eps=1e-10):
    return a / (b + eps)


def _auto_mndwi_threshold(mndwi: np.ndarray) -> float:
    p50 = np.nanpercentile(mndwi, 50)
    p85 = np.nanpercentile(mndwi, 85)
    auto_val = (p50 + p85) / 2
    print(f"[计算] 自动 MNDWI 阈值估计结果: {auto_val:.4f}")
    return auto_val

def run_jrc_extraction(
        bands: List[np.ndarray],
        params: Optional[JRCParams] = None
) -> np.ndarray | Tuple[np.ndarray, np.ndarray]:
    if len(bands) < 4:
        raise ValueError("JRC requires at least 4 bands")

    if params is None:
        params = JRCParams()

    print("\n" + "="*50)
    print("开始 JRC 水体提取算法调试日志")
    print("="*50)

    green = _normalize(bands[0], "Green (B2)")
    swir = _normalize(bands[1], "SWIR (B5)")
    nir = _normalize(bands[2], "NIR (B4)")
    red = _normalize(bands[3], "Red (B3)")
    blue = _normalize(bands[4], "Blue (B1)") if len(bands) > 4 else None

    mndwi = _safe_div(green - swir, green + swir)
    ndvi = _safe_div(nir - red, nir + red)

    threshold = params.mndwi_threshold
    if params.auto_threshold:
        threshold = _auto_mndwi_threshold(mndwi)
    rule_mndwi = mndwi > threshold
    p1 = np.mean(rule_mndwi) * 100
    print(f"[调试] 规则 1 (MNDWI > {threshold:.2f}) 通过率: {p1:.2f}%")
    rule_no_veg = ndvi < params.ndvi_max
    p2 = np.mean(rule_no_veg) * 100
    print(f"[调试] 规则 2 (NDVI < {params.ndvi_max}) 通过率: {p2:.2f}%")
    rule_low_nir = nir < params.nir_max
    p3 = np.mean(rule_low_nir) * 100
    print(f"[调试] 规则 3 (NIR < {params.nir_max}) 通过率: {p3:.2f}%")
    rule_shape = green > red
    p4 = np.mean(rule_shape) * 100
    print(f"[调试] 规则 4 (Green > Red) 通过率: {p4:.2f}%")
    if blue is not None:
        rule_blue = blue < green
        p5 = np.mean(rule_blue) * 100
        print(f"[调试] 规则 5 (Blue < Green) 通过率: {p5:.2f}%")
    else:
        rule_blue = True
        print(f"[调试] 规则 5 (Blue) 未提供波段，默认跳过")
    base_mask = (rule_mndwi & rule_no_veg & rule_low_nir & rule_shape & rule_blue)
    p_base = np.mean(base_mask) * 100
    print(f"----> [总结] 基础规则组综合通过率: {p_base:.4f}%")
    
    deep_water = (
            (mndwi > -0.1) &
            (nir < params.deep_nir_max) &
            (swir < params.deep_swir_max)
    )
    p_deep = np.mean(deep_water) * 100
    print(f"[调试] 规则 6 (深水增强模式) 通过率: {p_deep:.2f}%")

    final_mask = base_mask | deep_water
    p_final = np.mean(final_mask) * 100
    print(f"----> [总结] 最终合并结果通过率: {p_final:.4f}%")
    
    if p_final == 0:
        print("[警告] 结果为全 0！请检查数据量级和波段顺序。")
    print("="*50 + "\n")

    if not params.return_probability:
        return final_mask.astype("uint8")

    score = np.zeros_like(mndwi)
    score += np.clip((mndwi + 1) / 2, 0, 1) * 0.45
    score += np.clip(params.nir_max - nir, 0, params.nir_max) / params.nir_max * 0.30
    score += np.clip(params.ndvi_max - ndvi, 0, params.ndvi_max) / params.ndvi_max * 0.25
    probability = np.clip(score, 0, 1)

    return final_mask.astype("uint8"), probability

def jrc_water(
        bands: List[np.ndarray],
        threshold: float = 0.0,
        mode: str = "standard"
) -> np.ndarray:
    mode = mode.lower() if mode else "standard"
    params = JRCParams(mndwi_threshold=threshold)

    if mode == "auto":
        params.auto_threshold = True
    elif mode == "prob":
        params.return_probability = True
    elif mode == "strict":
        params.ndvi_max = 0.05
        params.nir_max = 0.12
    elif mode == "sensitive":
        params.ndvi_max = 0.15
        params.nir_max = 0.18

    result = run_jrc_extraction(bands, params)

    if isinstance(result, tuple):
        mask, _ = result
        return mask

    return result
