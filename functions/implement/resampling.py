import math
from typing import Literal

import rasterio
from pyproj import CRS
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.warp import reproject, transform_bounds


ResolutionUnit = Literal["source", "degrees", "meters"]


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


def _normalize_resolution(
    target_resolution_x: float,
    target_resolution_y: float | None,
) -> tuple[float, float]:
    x_res = float(target_resolution_x)
    y_res = float(target_resolution_y if target_resolution_y is not None else target_resolution_x)
    if x_res <= 0 or y_res <= 0:
        raise ValueError("Target resolution must be greater than zero")
    return x_res, y_res


def _normalize_unit(unit: str | None) -> ResolutionUnit:
    value = (unit or "source").strip().lower()
    if value not in {"source", "degrees", "meters"}:
        raise ValueError("resolution_unit must be one of: source, degrees, meters")
    return value  # type: ignore[return-value]


def _resampling_method(method: str | None) -> Resampling:
    value = (method or "bilinear").strip().lower()
    if value not in _RESAMPLING_METHODS:
        available = ", ".join(sorted(_RESAMPLING_METHODS))
        raise ValueError(f"Unsupported resampling method '{method}'. Available: {available}")
    return _RESAMPLING_METHODS[value]


def _local_meter_crs(src_crs: CRS, bounds) -> CRS:
    west, south, east, north = transform_bounds(src_crs, "EPSG:4326", *bounds, densify_pts=21)
    lon = (west + east) / 2
    lat = (south + north) / 2
    if not math.isfinite(lon) or not math.isfinite(lat) or lat < -80 or lat > 84:
        return CRS.from_epsg(3857)

    zone = min(60, max(1, int((lon + 180) // 6) + 1))
    epsg = (32600 if lat >= 0 else 32700) + zone
    return CRS.from_epsg(epsg)


def _uses_meter_units(crs: CRS) -> bool:
    if not crs.is_projected:
        return False
    axis_info = crs.axis_info or []
    if len(axis_info) < 2:
        return True
    return all(
        abs(float(getattr(axis, "unit_conversion_factor", 1.0)) - 1.0) < 1e-9
        for axis in axis_info[:2]
    )


def _target_crs(src_crs: CRS | None, bounds, unit: ResolutionUnit) -> CRS | None:
    if unit == "source":
        return src_crs
    if unit == "degrees":
        return CRS.from_epsg(4326)

    if src_crs is None:
        raise ValueError("Meter-based resampling requires a source CRS")
    if _uses_meter_units(src_crs):
        return src_crs
    return _local_meter_crs(src_crs, bounds)


def _target_bounds(src_crs: CRS | None, dst_crs: CRS | None, bounds) -> tuple[float, float, float, float]:
    if src_crs is None or dst_crs is None or src_crs.equals(dst_crs):
        return bounds.left, bounds.bottom, bounds.right, bounds.top
    return transform_bounds(src_crs, dst_crs, *bounds, densify_pts=21)


def resample_raster(
    input_path: str,
    output_path: str,
    target_resolution_x: float,
    target_resolution_y: float | None = None,
    resolution_unit: str = "source",
    resampling_method: str = "bilinear",
) -> dict[str, object]:
    """Resample a raster to a target pixel size in source units, degrees, or meters."""

    x_res, y_res = _normalize_resolution(target_resolution_x, target_resolution_y)
    unit = _normalize_unit(resolution_unit)
    resampling = _resampling_method(resampling_method)

    with rasterio.open(input_path) as src:
        src_crs = CRS.from_user_input(src.crs) if src.crs else None
        dst_crs = _target_crs(src_crs, src.bounds, unit)
        left, bottom, right, top = _target_bounds(src_crs, dst_crs, src.bounds)
        if right <= left or top <= bottom:
            raise ValueError("Raster bounds are invalid for resampling")

        dst_width = max(1, int(math.ceil((right - left) / x_res)))
        dst_height = max(1, int(math.ceil((top - bottom) / y_res)))
        dst_transform = from_origin(left, top, x_res, y_res)

        profile = src.profile.copy()
        profile.update(
            driver="GTiff",
            crs=dst_crs.to_string() if dst_crs else None,
            transform=dst_transform,
            width=dst_width,
            height=dst_height,
        )

        with rasterio.open(output_path, "w", **profile) as dst:
            if src_crs is None:
                data = src.read(
                    out_shape=(src.count, dst_height, dst_width),
                    resampling=resampling,
                )
                dst.write(data)
            else:
                for band_index in range(1, src.count + 1):
                    reproject(
                        source=rasterio.band(src, band_index),
                        destination=rasterio.band(dst, band_index),
                        src_transform=src.transform,
                        src_crs=src.crs,
                        src_nodata=src.nodata,
                        dst_transform=dst_transform,
                        dst_crs=dst_crs.to_string() if dst_crs else None,
                        dst_nodata=src.nodata,
                        resampling=resampling,
                    )

            for band_index, description in enumerate(src.descriptions, start=1):
                if description:
                    dst.set_band_description(band_index, description)

        return {
            "width": dst_width,
            "height": dst_height,
            "resolution": (x_res, y_res),
            "resolution_unit": unit,
            "crs": dst_crs.to_string() if dst_crs else None,
            "resampling_method": resampling_method,
        }
