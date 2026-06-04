from __future__ import annotations

import math
import os
from typing import Any

import rasterio
from affine import Affine
from rasterio.control import GroundControlPoint
from rasterio.enums import Resampling
from rasterio.transform import array_bounds, from_gcps, from_origin
from rasterio.warp import calculate_default_transform, reproject


_RESAMPLING_METHODS = {
    name: getattr(Resampling, name)
    for name in (
        "nearest",
        "bilinear",
        "cubic",
        "cubic_spline",
        "lanczos",
        "average",
        "mode",
        "max",
        "min",
        "med",
        "q1",
        "q3",
    )
    if hasattr(Resampling, name)
}


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
) -> dict[str, Any]:
    """Apply affine/GCP-based geometric correction and optional reprojection."""

    if scale_x <= 0 or scale_y <= 0:
        raise ValueError("scale_x and scale_y must be greater than zero")
    if target_resolution_x is not None and target_resolution_x <= 0:
        raise ValueError("target_resolution_x must be greater than zero")
    if target_resolution_y is not None and target_resolution_y <= 0:
        raise ValueError("target_resolution_y must be greater than zero")

    resampling = _resampling_method(resampling_method)

    with rasterio.open(input_path) as src:
        base_transform = _transform_from_gcps(gcps) if gcps else src.transform
        corrected_transform = _apply_affine_correction(
            base_transform,
            width=src.width,
            height=src.height,
            shift_x=shift_x,
            shift_y=shift_y,
            scale_x=scale_x,
            scale_y=scale_y,
            rotation_degrees=rotation_degrees,
        )

        dst_crs_value = dst_crs or (src.crs.to_string() if src.crs else None)
        should_warp = bool(dst_crs) or target_resolution_x is not None or target_resolution_y is not None

        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        if should_warp:
            if src.crs is None and dst_crs:
                raise ValueError("dst_crs reprojection requires the source raster to have a CRS")
            profile, dst_transform, width, height = _warped_profile(
                src,
                corrected_transform,
                dst_crs_value,
                target_resolution_x,
                target_resolution_y,
            )
            with rasterio.open(output_path, "w", **profile) as dst:
                if src.crs is None:
                    data = src.read(out_shape=(src.count, height, width), resampling=resampling)
                    dst.write(data)
                else:
                    for band_index in range(1, src.count + 1):
                        reproject(
                            source=rasterio.band(src, band_index),
                            destination=rasterio.band(dst, band_index),
                            src_transform=corrected_transform,
                            src_crs=src.crs,
                            src_nodata=src.nodata,
                            dst_transform=dst_transform,
                            dst_crs=dst_crs_value,
                            dst_nodata=src.nodata,
                            resampling=resampling,
                        )
                _copy_band_descriptions(src, dst)
                dst.update_tags(GEOMETRIC_CORRECTION="true", GEOMETRIC_METHOD=_method_name(gcps))
        else:
            profile = src.profile.copy()
            profile.update(driver="GTiff", transform=corrected_transform)
            with rasterio.open(output_path, "w", **profile) as dst:
                dst.write(src.read())
                _copy_band_descriptions(src, dst)
                dst.update_tags(GEOMETRIC_CORRECTION="true", GEOMETRIC_METHOD=_method_name(gcps))
            width, height = src.width, src.height
            dst_transform = corrected_transform

    return {
        "operation": "geometric_correction",
        "method": _method_name(gcps),
        "crs": dst_crs_value,
        "width": int(width),
        "height": int(height),
        "transform": list(dst_transform)[:6],
        "resampling_method": resampling_method,
        "shift": [float(shift_x), float(shift_y)],
        "scale": [float(scale_x), float(scale_y)],
        "rotation_degrees": float(rotation_degrees),
        "gcp_count": len(gcps or []),
    }


def _resampling_method(method: str | None) -> Resampling:
    value = (method or "bilinear").strip().lower()
    if value not in _RESAMPLING_METHODS:
        available = ", ".join(sorted(_RESAMPLING_METHODS))
        raise ValueError(f"Unsupported resampling method '{method}'. Available: {available}")
    return _RESAMPLING_METHODS[value]


def _transform_from_gcps(gcps: list[dict[str, float]] | None) -> Affine:
    if not gcps or len(gcps) < 3:
        raise ValueError("At least three GCPs are required to derive a geometric transform")
    points = []
    for gcp in gcps:
        try:
            points.append(
                GroundControlPoint(
                    row=float(gcp["row"]),
                    col=float(gcp["col"]),
                    x=float(gcp["x"]),
                    y=float(gcp["y"]),
                )
            )
        except KeyError as exc:
            raise ValueError("Each GCP must include row, col, x, and y") from exc
    return from_gcps(points)


def _apply_affine_correction(
    base: Affine,
    *,
    width: int,
    height: int,
    shift_x: float,
    shift_y: float,
    scale_x: float,
    scale_y: float,
    rotation_degrees: float,
) -> Affine:
    if (
        abs(shift_x) < 1e-12
        and abs(shift_y) < 1e-12
        and abs(scale_x - 1.0) < 1e-12
        and abs(scale_y - 1.0) < 1e-12
        and abs(rotation_degrees) < 1e-12
    ):
        return base

    center_x, center_y = base * (width / 2.0, height / 2.0)
    correction = (
        Affine.translation(center_x + shift_x, center_y + shift_y)
        * Affine.rotation(rotation_degrees)
        * Affine.scale(scale_x, scale_y)
        * Affine.translation(-center_x, -center_y)
    )
    return correction * base


def _warped_profile(
    src: rasterio.DatasetReader,
    corrected_transform: Affine,
    dst_crs: str | None,
    target_resolution_x: float | None,
    target_resolution_y: float | None,
) -> tuple[dict[str, Any], Affine, int, int]:
    left, bottom, right, top = _ordered_bounds(array_bounds(src.height, src.width, corrected_transform))
    resolution = _resolution_tuple(target_resolution_x, target_resolution_y)

    if src.crs is None:
        if resolution is None:
            resolution = (abs(corrected_transform.a), abs(corrected_transform.e))
        width = max(1, int(math.ceil((right - left) / resolution[0])))
        height = max(1, int(math.ceil((top - bottom) / resolution[1])))
        dst_transform = from_origin(left, top, resolution[0], resolution[1])
    else:
        dst_transform, width, height = calculate_default_transform(
            src.crs,
            dst_crs or src.crs,
            src.width,
            src.height,
            left,
            bottom,
            right,
            top,
            resolution=resolution,
        )

    profile = src.profile.copy()
    profile.update(
        driver="GTiff",
        crs=dst_crs,
        transform=dst_transform,
        width=width,
        height=height,
    )
    return profile, dst_transform, width, height


def _resolution_tuple(x_res: float | None, y_res: float | None) -> tuple[float, float] | None:
    if x_res is None and y_res is None:
        return None
    x_value = float(x_res if x_res is not None else y_res)
    y_value = float(y_res if y_res is not None else x_value)
    if x_value <= 0 or y_value <= 0:
        raise ValueError("Target resolution must be greater than zero")
    return x_value, y_value


def _ordered_bounds(bounds: tuple[float, float, float, float]) -> tuple[float, float, float, float]:
    left, bottom, right, top = bounds
    west, east = sorted((left, right))
    south, north = sorted((bottom, top))
    return west, south, east, north


def _copy_band_descriptions(src: rasterio.DatasetReader, dst: rasterio.DatasetWriter) -> None:
    for band_index, description in enumerate(src.descriptions, start=1):
        if description:
            dst.set_band_description(band_index, description)


def _method_name(gcps: list[dict[str, float]] | None) -> str:
    return "gcp_affine" if gcps else "affine"
