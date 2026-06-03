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
    dos_percentile: float = 1.0   # DOS text,text 1%


def _dos_correction(arr: np.ndarray, name: str, percentile: float = 1.0) -> np.ndarray:
    """
    Dark Object Subtraction (DOS) text.
    text percentile% text,text.
    used for Landsat Level-1 DN text.
    """
    dark = np.nanpercentile(arr, percentile)
    corrected = arr - dark
    corrected = np.clip(corrected, 0, None)
    print(f"  --> {name} DOS text: text = {dark:.2f},"
          f"text = {np.nanmean(corrected):.2f}")
    return corrected


def _detect_and_scale(arr: np.ndarray, name: str,
                      dos_percentile: float = 1.0) -> Tuple[np.ndarray, str]:
    """
    text,L1 text DOS text.
    return (text, text)
      text: "norm" | "8bit" | "L2" | "L1" | "unknown"
    """
    raw_max  = np.nanmax(arr)
    raw_mean = np.nanmean(arr)

    # text
    if raw_max <= 1.0:
        print(f"  --> {name} text,text")
        return arr, "norm"

    # 8-bit DN
    if raw_max <= 255:
        print(f"  --> {name} text 8-bit DN,text / 255")
        return arr / 255.0, "8bit"

    # Level-2 table uint16(max <= 12000,text 200~3000)
    if raw_max <= 12000 and 200 <= raw_mean <= 3000:
        print(f"  --> {name} text Level-2 text (uint16),text / 10000")
        return arr / 10000.0, "L2"

    # Level-1 DN uint16 - text DOS text,text
    if raw_max > 12000:
        arr = _dos_correction(arr, name, dos_percentile)
        print(f"  --> {name} text Level-1 DN (uint16),DOS text / 65535")
        return arr / 65535.0, "L1"

    # text min-max
    raw_min = np.nanmin(arr)
    print(f"  [text] {name} text (max={raw_max:.0f}, mean={raw_mean:.0f}),"
          f"uses min-max text,result!")
    return (arr - raw_min) / (raw_max - raw_min + 1e-10), "unknown"


def _normalize(arr: np.ndarray, name: str = "Band",
               dos_percentile: float = 1.0) -> Tuple[np.ndarray, str]:
    arr = arr.astype(float)

    # text nodata(0 text 65535)
    arr[arr == 0]     = np.nan
    arr[arr >= 65535] = np.nan

    raw_max  = np.nanmax(arr)
    raw_mean = np.nanmean(arr)
    print(f"[text] {name} - text: {raw_max:.4f}, text: {raw_mean:.4f}")

    arr, dtype_tag = _detect_and_scale(arr, name, dos_percentile)

    scaled_mean = np.nanmean(arr)
    print(f"  --> {name} text: {scaled_mean:.4f}")
    if scaled_mean > 0.5:
        print(f"  [text] {name} text = {scaled_mean:.4f},text(text < 0.3),"
              f"text Level-2 text")

    return arr, dtype_tag


def _safe_div(a, b, eps=1e-10):
    return a / (b + eps)


def _auto_mndwi_threshold(mndwi: np.ndarray) -> float:
    p50 = np.nanpercentile(mndwi, 50)
    p85 = np.nanpercentile(mndwi, 85)
    auto_val = (p50 + p85) / 2
    print(f"[text] text MNDWI result: {auto_val:.4f}")
    return auto_val


def run_jrc_extraction(
        bands: List[np.ndarray],
        params: Optional[JRCParams] = None
) -> np.ndarray | Tuple[np.ndarray, np.ndarray]:
    if len(bands) < 4:
        raise ValueError("JRC requires at least 4 bands")

    if params is None:
        params = JRCParams()

    print("\n" + "=" * 50)
    print("text JRC extraction")
    print("=" * 50)

    dos_p = params.dos_percentile
    green, green_tag = _normalize(bands[0], "Green (B2)", dos_p)
    swir,  swir_tag  = _normalize(bands[1], "SWIR (B5)",  dos_p)
    nir,   nir_tag   = _normalize(bands[2], "NIR (B4)",   dos_p)
    red,   red_tag   = _normalize(bands[3], "Red (B3)",   dos_p)

    if len(bands) > 4:
        blue, blue_tag = _normalize(bands[4], "Blue (B1)", dos_p)
    else:
        blue, blue_tag = None, None

    # text
    tags = {green_tag, swir_tag, nir_tag, red_tag}
    if blue_tag:
        tags.add(blue_tag)
    if len(tags) > 1:
        print(f"[text] do not match: {tags},text!")
    else:
        print(f"[text] text: {tags.pop()}")

    mndwi = _safe_div(green - swir, green + swir)
    ndvi  = _safe_div(nir - red,   nir + red)

    threshold = params.mndwi_threshold
    if params.auto_threshold:
        threshold = _auto_mndwi_threshold(mndwi)

    rule_mndwi   = mndwi > threshold
    rule_no_veg  = ndvi  < params.ndvi_max
    rule_low_nir = nir   < params.nir_max
    rule_shape   = green > red

    p1 = np.nanmean(rule_mndwi)   * 100
    p2 = np.nanmean(rule_no_veg)  * 100
    p3 = np.nanmean(rule_low_nir) * 100
    p4 = np.nanmean(rule_shape)   * 100

    print(f"[text] text 1 (MNDWI > {threshold:.2f}) through: {p1:.2f}%")
    print(f"[text] text 2 (NDVI  < {params.ndvi_max})  through: {p2:.2f}%")
    print(f"[text] text 3 (NIR   < {params.nir_max})  through: {p3:.2f}%")
    print(f"[text] text 4 (Green > Red)               through: {p4:.2f}%")

    # text 5:L1 text DOS text,text
    if blue is not None:
        if blue_tag == "L1":
            # DOS text,text blue < green * 1.1
            rule_blue = blue < green * 1.1
            p5 = np.nanmean(rule_blue) * 100
            print(f"[text] text 5 (Blue < Green*1.1) L1-DOS text through: {p5:.2f}%")
        else:
            rule_blue = blue < green
            p5 = np.nanmean(rule_blue) * 100
            print(f"[text] text 5 (Blue < Green) through: {p5:.2f}%")
    else:
        rule_blue = True
        print(f"[text] text 5 (Blue) text,text")

    base_mask = (rule_mndwi & rule_no_veg & rule_low_nir & rule_shape & rule_blue)
    p_base = np.nanmean(base_mask) * 100
    print(f"----> [text] through: {p_base:.4f}%")

    # text:DOS text NIR/SWIR text,text
    deep_nir_t  = params.deep_nir_max  * 1.5 if green_tag == "L1" else params.deep_nir_max
    deep_swir_t = params.deep_swir_max * 1.5 if swir_tag  == "L1" else params.deep_swir_max
    deep_water = (
        (mndwi > -0.1) &
        (nir   < deep_nir_t) &
        (swir  < deep_swir_t)
    )
    p_deep = np.nanmean(deep_water) * 100
    print(f"[text] text 6 (text NIR<{deep_nir_t:.3f} SWIR<{deep_swir_t:.3f}) through: {p_deep:.2f}%")

    final_mask = base_mask | deep_water
    p_final = np.nanmean(final_mask) * 100
    print(f"----> [text] resultthrough: {p_final:.4f}%")

    if p_final == 0:
        print("[text] result 0!order.")
    elif p_final > 20:
        print(f"[text] resultthrough {p_final:.2f}% text,text,text DOS text")
    print("=" * 50 + "\n")

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
        params.nir_max  = 0.12
    elif mode == "sensitive":
        params.ndvi_max = 0.15
        params.nir_max  = 0.18

    result = run_jrc_extraction(bands, params)

    if isinstance(result, tuple):
        mask, _ = result
        return mask

    return result