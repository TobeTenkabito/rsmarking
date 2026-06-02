from __future__ import annotations

import os
from typing import Any, Literal

import numpy as np
import rasterio


AtmosphericMethod = Literal[
    "auto",
    "surface_reflectance",
    "metadata_scale",
    "dos1",
    "quac",
    "lasrc",
    "ledaps",
    "sen2cor",
    "modis_sr",
    "flaash",
    "sixs",
]


_SCALE_ALIASES = {
    "surface_reflectance",
    "metadata_scale",
    "lasrc",
    "ledaps",
    "sen2cor",
    "modis_sr",
    "flaash",
    "sixs",
}


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
) -> dict[str, Any]:
    """Create a surface-reflectance GeoTIFF with mainstream product compatibility.

    The implementation supports two practical paths:
    - official surface-reflectance products are normalized with product-aware
      scale/offset rules, compatible with LaSRC, LEDAPS, Sen2Cor, MODIS SR,
      and external FLAASH/QUAC/6S products;
    - raw/TOA-like inputs can be corrected with empirical DOS1 or QUAC-style
      scene normalization.
    """

    normalized_method = _normalize_method(method)
    dark_percentile = _bounded_percentile(dark_percentile, "dark_percentile")
    bright_percentile = _bounded_percentile(bright_percentile, "bright_percentile")
    if bright_percentile <= dark_percentile:
        raise ValueError("bright_percentile must be greater than dark_percentile")

    with rasterio.open(input_path) as src:
        detected = _detect_product(src, input_path, sensor)
        chosen_method = _choose_method(normalized_method, detected)
        factor, bias = _resolve_scale_offset(
            src,
            detected,
            chosen_method,
            scale_factor,
            offset,
        )

        profile = src.profile.copy()
        profile.update(driver="GTiff", dtype="float32", nodata=-9999.0)

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with rasterio.open(output_path, "w", **profile) as dst:
            for band_index in range(1, src.count + 1):
                source = src.read(band_index, masked=True).astype("float32")
                reflectance = source * factor + bias

                if chosen_method == "dos1":
                    corrected = _dos1(reflectance, dark_percentile)
                elif chosen_method == "quac":
                    corrected = _quac(reflectance, dark_percentile, bright_percentile)
                else:
                    corrected = reflectance

                if clamp:
                    corrected = np.ma.clip(corrected, 0.0, 1.0)

                output = corrected.filled(-9999.0).astype("float32")
                dst.write(output, band_index)
                if src.descriptions[band_index - 1]:
                    dst.set_band_description(band_index, src.descriptions[band_index - 1])

            dst.update_tags(
                ATMOSPHERIC_CORRECTION="true",
                ATMOSPHERIC_METHOD=chosen_method,
                ATMOSPHERIC_COMPATIBILITY=detected["compatibility"],
                ATMOSPHERIC_SENSOR=detected["sensor"],
                ATMOSPHERIC_SCALE_FACTOR=str(factor),
                ATMOSPHERIC_OFFSET=str(bias),
            )

    return {
        "method": chosen_method,
        "sensor": detected["sensor"],
        "compatibility": detected["compatibility"],
        "scale_factor": factor,
        "offset": bias,
        "dark_percentile": dark_percentile,
        "bright_percentile": bright_percentile,
        "output_dtype": "float32",
        "nodata": -9999.0,
    }


def _normalize_method(method: str | None) -> str:
    value = (method or "auto").strip().lower()
    if value not in AtmosphericMethod.__args__:  # type: ignore[attr-defined]
        available = ", ".join(AtmosphericMethod.__args__)  # type: ignore[attr-defined]
        raise ValueError(f"Unsupported atmospheric correction method '{method}'. Available: {available}")
    return value


def _bounded_percentile(value: float, name: str) -> float:
    percentile = float(value)
    if percentile < 0 or percentile > 100:
        raise ValueError(f"{name} must be between 0 and 100")
    return percentile


def _choose_method(method: str, detected: dict[str, str]) -> str:
    if method == "auto":
        return "metadata_scale" if detected["surface_reflectance"] == "true" else "dos1"
    if method in _SCALE_ALIASES:
        return "metadata_scale"
    return method


def _detect_product(src: rasterio.DatasetReader, input_path: str, sensor: str) -> dict[str, str]:
    text = " ".join(
        str(item).lower()
        for item in [
            input_path,
            os.path.basename(input_path),
            sensor,
            *src.tags().keys(),
            *src.tags().values(),
            *[desc or "" for desc in src.descriptions],
        ]
    )

    detected_sensor = (sensor or "auto").strip().lower()
    compatibility = "generic"
    surface_reflectance = False

    if detected_sensor == "auto":
        detected_sensor = "generic"
        if any(marker in text for marker in ("landsat", "lc08", "lc09", "le07", "lt05", "sr_b")):
            detected_sensor = "landsat"
        elif any(marker in text for marker in ("sentinel-2", "sentinel2", "s2a", "s2b", "msil2a", "sen2cor")):
            detected_sensor = "sentinel2"
        elif any(marker in text for marker in ("mod09", "myd09", "mcd43", "modis")):
            detected_sensor = "modis"
        elif any(marker in text for marker in ("gaofen", "gf1", "gf2", "gf6", "flaash", "quac", "6s")):
            detected_sensor = "gaofen"

    if detected_sensor == "landsat":
        compatibility = "Landsat LaSRC/LEDAPS"
        surface_reflectance = any(marker in text for marker in ("lasrc", "ledaps", "level-2", "level2", "l2sp", "sr_b"))
    elif detected_sensor == "sentinel2":
        compatibility = "Sentinel-2 Sen2Cor"
        surface_reflectance = any(marker in text for marker in ("l2a", "msil2a", "sen2cor", "scl"))
    elif detected_sensor == "modis":
        compatibility = "MODIS Official Surface Reflectance"
        surface_reflectance = any(marker in text for marker in ("mod09", "myd09", "mcd43", "surface reflectance"))
    elif detected_sensor == "gaofen":
        compatibility = "Gaofen FLAASH/QUAC/6S"
        surface_reflectance = any(marker in text for marker in ("flaash", "quac", "6s", "surface reflectance", "sr"))

    if any(marker in text for marker in ("surface_reflectance", "surface reflectance", "reflectance")):
        surface_reflectance = True

    return {
        "sensor": detected_sensor,
        "compatibility": compatibility,
        "surface_reflectance": "true" if surface_reflectance else "false",
    }


def _resolve_scale_offset(
    src: rasterio.DatasetReader,
    detected: dict[str, str],
    method: str,
    scale_factor: float | None,
    offset: float | None,
) -> tuple[float, float]:
    if scale_factor is not None:
        return float(scale_factor), float(offset or 0.0)

    sample = _sample_valid_pixels(src)
    if sample.size and np.nanmax(sample) <= 2.0 and np.nanmin(sample) >= -1.0:
        return 1.0, float(offset or 0.0)

    sensor = detected["sensor"]
    tags_text = " ".join(str(value).lower() for value in src.tags().values())
    if sensor == "landsat" and any(marker in tags_text for marker in ("collection 2", "l2sp", "lasrc")):
        return 0.0000275, float(-0.2 if offset is None else offset)

    if sensor in {"landsat", "sentinel2", "modis", "gaofen"}:
        return 0.0001, float(offset or 0.0)

    if method in {"dos1", "quac"} and sample.size and np.nanpercentile(sample, 99) > 10:
        return 0.0001, float(offset or 0.0)

    return 1.0, float(offset or 0.0)


def _sample_valid_pixels(src: rasterio.DatasetReader, max_size: int = 256) -> np.ndarray:
    out_height = min(src.height, max_size)
    out_width = min(src.width, max_size)
    sample = src.read(
        1,
        out_shape=(out_height, out_width),
        masked=True,
    ).astype("float32")
    compressed = sample.compressed()
    if compressed.size == 0:
        return np.array([], dtype="float32")
    return compressed


def _dos1(data: np.ma.MaskedArray, dark_percentile: float) -> np.ma.MaskedArray:
    valid = data.compressed()
    if valid.size == 0:
        return data
    dark_object = float(np.nanpercentile(valid, dark_percentile))
    return data - max(dark_object, 0.0)


def _quac(
    data: np.ma.MaskedArray,
    dark_percentile: float,
    bright_percentile: float,
) -> np.ma.MaskedArray:
    valid = data.compressed()
    if valid.size == 0:
        return data
    dark = float(np.nanpercentile(valid, dark_percentile))
    bright = float(np.nanpercentile(valid, bright_percentile))
    if bright <= dark:
        return data - dark
    return (data - dark) / (bright - dark)
