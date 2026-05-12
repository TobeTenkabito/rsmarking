import math
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling


def _finite_values(data: np.ma.MaskedArray) -> np.ndarray:
    values = np.ma.compressed(data)
    if values.size == 0:
        return values.astype("float64")

    if np.iscomplexobj(values):
        values = np.abs(values)

    values = values.astype("float64", copy=False)
    return values[np.isfinite(values)]


def _safe_float(value: Any) -> float | None:
    if value is None:
        return None
    numeric = float(value)
    if math.isfinite(numeric):
        return numeric
    return None


def _histogram(values: np.ndarray, bins: int) -> dict:
    if values.size == 0:
        return {"counts": [], "edges": [], "bins": []}

    counts, edges = np.histogram(values, bins=bins)
    total = int(values.size)
    return {
        "counts": [int(v) for v in counts.tolist()],
        "edges": [_safe_float(v) for v in edges.tolist()],
        "bins": [
            {
                "start": _safe_float(edges[i]),
                "end": _safe_float(edges[i + 1]),
                "count": int(counts[i]),
                "percent": float(counts[i] / total * 100) if total else 0.0,
            }
            for i in range(len(counts))
        ],
    }


def _band_name(src: rasterio.DatasetReader, band_index: int) -> str:
    description = src.descriptions[band_index - 1]
    return description or f"Band {band_index}"


def _band_stats(
    src: rasterio.DatasetReader,
    band_index: int,
    out_height: int,
    out_width: int,
    bins: int,
) -> dict:
    data = src.read(
        band_index,
        out_shape=(out_height, out_width),
        masked=True,
        resampling=Resampling.nearest,
    )
    data = np.ma.masked_invalid(data)
    values = _finite_values(data)

    sample_count = int(out_height * out_width)
    valid_count = int(values.size)
    nodata_count = max(0, sample_count - valid_count)

    if valid_count == 0:
        return {
            "index": band_index,
            "name": _band_name(src, band_index),
            "dtype": src.dtypes[band_index - 1],
            "valid_count": 0,
            "nodata_count": nodata_count,
            "valid_percent": 0.0,
            "min": None,
            "max": None,
            "mean": None,
            "std": None,
            "median": None,
            "p2": None,
            "p98": None,
            "histogram": {"counts": [], "edges": [], "bins": []},
        }

    p2, median, p98 = np.percentile(values, [2, 50, 98])
    return {
        "index": band_index,
        "name": _band_name(src, band_index),
        "dtype": src.dtypes[band_index - 1],
        "valid_count": valid_count,
        "nodata_count": nodata_count,
        "valid_percent": float(valid_count / sample_count * 100) if sample_count else 0.0,
        "min": _safe_float(np.min(values)),
        "max": _safe_float(np.max(values)),
        "mean": _safe_float(np.mean(values)),
        "std": _safe_float(np.std(values)),
        "median": _safe_float(median),
        "p2": _safe_float(p2),
        "p98": _safe_float(p98),
        "histogram": _histogram(values, bins),
    }


def compute_raster_statistics(
    file_path: str,
    *,
    bins: int = 32,
    max_size: int = 768,
    band_indices: list[int] | None = None,
) -> dict:
    """Compute sampled per-band statistics for frontend visualization."""
    bins = max(4, min(int(bins), 128))
    max_size = max(128, min(int(max_size), 2048))

    with rasterio.open(file_path) as src:
        scale = max(1.0, src.width / max_size, src.height / max_size)
        out_width = max(1, int(round(src.width / scale)))
        out_height = max(1, int(round(src.height / scale)))

        if band_indices is None:
            selected_bands = list(range(1, src.count + 1))
        else:
            selected_bands = [int(b) for b in band_indices]
            invalid = [b for b in selected_bands if b < 1 or b > src.count]
            if invalid:
                raise ValueError(
                    f"Band index out of range: {invalid}. Raster has {src.count} band(s)."
                )

        bands = [
            _band_stats(src, band_index, out_height, out_width, bins)
            for band_index in selected_bands
        ]

        return {
            "width": src.width,
            "height": src.height,
            "band_count": src.count,
            "crs": src.crs.to_string() if src.crs else None,
            "data_type": src.dtypes[0] if src.dtypes else None,
            "nodata": _safe_float(src.nodata),
            "sample": {
                "width": out_width,
                "height": out_height,
                "pixel_count": int(out_width * out_height),
                "scale": float(scale),
                "is_full_resolution": scale <= 1.0,
            },
            "bands": bands,
        }
