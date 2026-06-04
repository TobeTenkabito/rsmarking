from __future__ import annotations

import math
import os
from typing import Any, Literal

import numpy as np
import rasterio


RadiometricCalibrationType = Literal["auto", "radiance", "reflectance", "scale"]


def radiometric_calibration(
    input_path: str,
    output_path: str,
    calibration_type: RadiometricCalibrationType = "auto",
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
) -> dict[str, Any]:
    """Convert raster DN values into calibrated radiance or reflectance.

    The implementation favors explicit parameters, then common product tags
    such as Landsat MTL-derived RADIANCE_MULT/ADD and REFLECTANCE_MULT/ADD.
    """

    mode = _normalize_calibration_type(calibration_type)
    if earth_sun_distance <= 0:
        raise ValueError("earth_sun_distance must be greater than zero")

    band_summaries: list[dict[str, Any]] = []

    with rasterio.open(input_path) as src:
        profile = src.profile.copy()
        profile.update(driver="GTiff", dtype="float32", nodata=-9999.0)
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)

        dataset_tags = _upper_tags(src.tags())
        with rasterio.open(output_path, "w", **profile) as dst:
            for band_index in range(1, src.count + 1):
                band_tags = {**dataset_tags, **_upper_tags(src.tags(band_index))}
                params = _resolve_band_params(
                    band_index=band_index,
                    tags=band_tags,
                    mode=mode,
                    scale_factor=scale_factor,
                    offset=offset,
                    radiance_mult=radiance_mult,
                    radiance_add=radiance_add,
                    reflectance_mult=reflectance_mult,
                    reflectance_add=reflectance_add,
                    sun_elevation=sun_elevation,
                    solar_irradiance=solar_irradiance,
                )
                chosen = _choose_mode(mode, params)

                source = src.read(band_index, masked=True).astype("float32")
                calibrated = _calibrate_band(
                    source,
                    chosen,
                    params,
                    earth_sun_distance=earth_sun_distance,
                    sun_elevation_correction=sun_elevation_correction,
                    clamp=clamp,
                )
                dst.write(calibrated.filled(-9999.0).astype("float32"), band_index)
                if src.descriptions[band_index - 1]:
                    dst.set_band_description(band_index, src.descriptions[band_index - 1])

                band_summaries.append({
                    "band": band_index,
                    "mode": chosen,
                    "scale": params.get("scale"),
                    "offset": params.get("offset"),
                    "radiance_mult": params.get("radiance_mult"),
                    "radiance_add": params.get("radiance_add"),
                    "reflectance_mult": params.get("reflectance_mult"),
                    "reflectance_add": params.get("reflectance_add"),
                })

            dst.update_tags(
                RADIOMETRIC_CALIBRATION="true",
                RADIOMETRIC_TYPE=mode,
                RADIOMETRIC_CLAMP=str(bool(clamp)).lower(),
            )

    return {
        "operation": "radiometric_calibration",
        "calibration_type": mode,
        "output_dtype": "float32",
        "nodata": -9999.0,
        "band_count": len(band_summaries),
        "bands": band_summaries,
    }


def _normalize_calibration_type(value: str | None) -> RadiometricCalibrationType:
    normalized = (value or "auto").strip().lower()
    if normalized not in {"auto", "radiance", "reflectance", "scale"}:
        raise ValueError("calibration_type must be one of: auto, radiance, reflectance, scale")
    return normalized  # type: ignore[return-value]


def _upper_tags(tags: dict[str, Any]) -> dict[str, str]:
    return {str(key).upper(): str(value) for key, value in (tags or {}).items()}


def _resolve_band_params(
    *,
    band_index: int,
    tags: dict[str, str],
    mode: RadiometricCalibrationType,
    scale_factor: float | None,
    offset: float | None,
    radiance_mult: float | None,
    radiance_add: float | None,
    reflectance_mult: float | None,
    reflectance_add: float | None,
    sun_elevation: float | None,
    solar_irradiance: float | None,
) -> dict[str, float | None]:
    del mode
    return {
        "scale": _first_float(scale_factor, tags, f"SCALE_FACTOR_BAND_{band_index}", "SCALE_FACTOR", "SCALE"),
        "offset": _first_float(offset, tags, f"OFFSET_BAND_{band_index}", "OFFSET", "ADD_OFFSET"),
        "radiance_mult": _first_float(
            radiance_mult,
            tags,
            f"RADIANCE_MULT_BAND_{band_index}",
            f"RADIANCE_MULT_BAND_{band_index:02d}",
            "RADIANCE_MULT",
            "GAIN",
        ),
        "radiance_add": _first_float(
            radiance_add,
            tags,
            f"RADIANCE_ADD_BAND_{band_index}",
            f"RADIANCE_ADD_BAND_{band_index:02d}",
            "RADIANCE_ADD",
            "BIAS",
        ),
        "reflectance_mult": _first_float(
            reflectance_mult,
            tags,
            f"REFLECTANCE_MULT_BAND_{band_index}",
            f"REFLECTANCE_MULT_BAND_{band_index:02d}",
            "REFLECTANCE_MULT",
        ),
        "reflectance_add": _first_float(
            reflectance_add,
            tags,
            f"REFLECTANCE_ADD_BAND_{band_index}",
            f"REFLECTANCE_ADD_BAND_{band_index:02d}",
            "REFLECTANCE_ADD",
        ),
        "sun_elevation": _first_float(sun_elevation, tags, "SUN_ELEVATION", "SUN_ELEVATION_ANGLE"),
        "solar_irradiance": _first_float(
            solar_irradiance,
            tags,
            f"SOLAR_IRRADIANCE_BAND_{band_index}",
            f"ESUN_BAND_{band_index}",
            "SOLAR_IRRADIANCE",
            "ESUN",
        ),
    }


def _first_float(explicit: float | None, tags: dict[str, str], *names: str) -> float | None:
    if explicit is not None:
        return float(explicit)
    for name in names:
        raw = tags.get(name.upper())
        if raw is None:
            continue
        try:
            return float(raw)
        except ValueError:
            continue
    return None


def _choose_mode(mode: RadiometricCalibrationType, params: dict[str, float | None]) -> str:
    if mode != "auto":
        return mode
    if params.get("reflectance_mult") is not None or params.get("reflectance_add") is not None:
        return "reflectance"
    if params.get("radiance_mult") is not None or params.get("radiance_add") is not None:
        return "radiance"
    if params.get("scale") is not None or params.get("offset") is not None:
        return "scale"
    return "scale"


def _calibrate_band(
    source: np.ma.MaskedArray,
    mode: str,
    params: dict[str, float | None],
    *,
    earth_sun_distance: float,
    sun_elevation_correction: bool,
    clamp: bool,
) -> np.ma.MaskedArray:
    if mode == "reflectance":
        mult = params.get("reflectance_mult")
        add = params.get("reflectance_add")
        if mult is not None or add is not None:
            calibrated = source * float(mult if mult is not None else 1.0) + float(add if add is not None else 0.0)
        else:
            radiance = _radiance(source, params)
            calibrated = _radiance_to_reflectance(radiance, params, earth_sun_distance)

        sun_elevation = params.get("sun_elevation")
        if sun_elevation_correction and sun_elevation is not None:
            sin_elevation = math.sin(math.radians(float(sun_elevation)))
            if sin_elevation <= 0:
                raise ValueError("sun_elevation must be greater than zero for sun-angle correction")
            calibrated = calibrated / sin_elevation
    elif mode == "radiance":
        calibrated = _radiance(source, params)
    else:
        calibrated = source * _coalesce(params.get("scale"), 1.0) + _coalesce(params.get("offset"), 0.0)

    if clamp:
        calibrated = np.ma.clip(calibrated, 0.0, 1.0)
    return calibrated.astype("float32")


def _radiance(source: np.ma.MaskedArray, params: dict[str, float | None]) -> np.ma.MaskedArray:
    return source * _coalesce(params.get("radiance_mult"), params.get("scale"), 1.0) + _coalesce(
        params.get("radiance_add"), params.get("offset"), 0.0
    )


def _coalesce(*values: float | None) -> float:
    for value in values:
        if value is not None:
            return float(value)
    raise ValueError("At least one fallback value is required")


def _radiance_to_reflectance(
    radiance: np.ma.MaskedArray,
    params: dict[str, float | None],
    earth_sun_distance: float,
) -> np.ma.MaskedArray:
    sun_elevation = params.get("sun_elevation")
    solar_irradiance = params.get("solar_irradiance")
    if sun_elevation is None or solar_irradiance is None:
        return radiance
    sin_elevation = math.sin(math.radians(float(sun_elevation)))
    if sin_elevation <= 0:
        raise ValueError("sun_elevation must be greater than zero for radiance-to-reflectance conversion")
    return (math.pi * radiance * earth_sun_distance * earth_sun_distance) / (float(solar_irradiance) * sin_elevation)
