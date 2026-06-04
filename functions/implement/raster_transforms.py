from __future__ import annotations

import math
import os
from typing import Any, Literal

import numpy as np
import rasterio


TransformType = Literal["fourier", "wavelet", "pca"]
FourierOutput = Literal["magnitude", "power", "phase"]
WaveletOutput = Literal["detail_energy", "approximation", "horizontal", "vertical", "diagonal"]

_FLOAT_NODATA = -9999.0


def raster_transform_analysis(
    input_path: str,
    output_path: str,
    transform_type: str,
    band_index: int = 1,
    fourier_output: str = "magnitude",
    wavelet_output: str = "detail_energy",
    wavelet_level: int = 1,
    pca_components: int = 3,
    pca_standardize: bool = False,
) -> dict[str, Any]:
    """Create Fourier, Haar wavelet, or PCA raster analysis products."""

    analysis_type = _normalize_transform_type(transform_type)
    with rasterio.open(input_path) as src:
        if analysis_type == "pca":
            data, valid_mask = _read_stack(src)
            result, descriptions, meta = _pca(data, valid_mask, pca_components, pca_standardize)
            profile = src.profile.copy()
            output = _prepare_float_output(result, valid_mask)
            _write_stack(output_path, profile, output, descriptions)
            return {
                "operation": "raster_transform_analysis",
                "transform_type": analysis_type,
                **meta,
                "width": int(output.shape[2]),
                "height": int(output.shape[1]),
                "bands": int(output.shape[0]),
            }

        if band_index < 1 or band_index > src.count:
            raise ValueError(f"Raster has {src.count} bands; band_index {band_index} is out of range")
        band, valid_mask = _read_band(src, band_index)
        profile = src.profile.copy()

    if analysis_type == "fourier":
        output_name = _normalize_fourier_output(fourier_output)
        result = _fourier(band, valid_mask, output_name)
        descriptions = [f"Fourier {output_name}"]
        meta = {"fourier_output": output_name}
        output_valid_mask = np.ones_like(valid_mask, dtype=bool)
    elif analysis_type == "wavelet":
        output_name = _normalize_wavelet_output(wavelet_output)
        result = _wavelet(band, valid_mask, output_name, wavelet_level)
        descriptions = [f"Haar wavelet {output_name}"]
        meta = {"wavelet_output": output_name, "wavelet_level": int(wavelet_level)}
        output_valid_mask = valid_mask
    else:
        raise ValueError(f"Unsupported transform_type: {transform_type}")

    output = _prepare_float_output(result[np.newaxis, :, :], output_valid_mask)
    _write_stack(output_path, profile, output, descriptions)
    return {
        "operation": "raster_transform_analysis",
        "transform_type": analysis_type,
        "band_index": int(band_index),
        "width": int(output.shape[2]),
        "height": int(output.shape[1]),
        "bands": int(output.shape[0]),
        **meta,
    }


def _normalize_transform_type(transform_type: str) -> TransformType:
    value = str(transform_type or "").strip().lower().replace("-", "_")
    aliases = {
        "fft": "fourier",
        "fourier_analysis": "fourier",
        "wavelet_analysis": "wavelet",
        "principal_component_analysis": "pca",
        "principal_components": "pca",
    }
    value = aliases.get(value, value)
    if value not in {"fourier", "wavelet", "pca"}:
        raise ValueError("transform_type must be one of: fourier, wavelet, pca")
    return value  # type: ignore[return-value]


def _normalize_fourier_output(output: str) -> FourierOutput:
    value = str(output or "magnitude").strip().lower()
    if value not in {"magnitude", "power", "phase"}:
        raise ValueError("fourier_output must be magnitude, power, or phase")
    return value  # type: ignore[return-value]


def _normalize_wavelet_output(output: str) -> WaveletOutput:
    value = str(output or "detail_energy").strip().lower().replace("-", "_")
    if value in {"energy", "detail"}:
        value = "detail_energy"
    if value not in {"detail_energy", "approximation", "horizontal", "vertical", "diagonal"}:
        raise ValueError("wavelet_output must be detail_energy, approximation, horizontal, vertical, or diagonal")
    return value  # type: ignore[return-value]


def _read_band(src: rasterio.DatasetReader, band_index: int) -> tuple[np.ndarray, np.ndarray]:
    data = src.read(band_index, masked=True).astype("float32")
    band = np.asarray(data.filled(np.nan), dtype="float32")
    valid_mask = ~np.ma.getmaskarray(data) & np.isfinite(band)
    if not np.any(valid_mask):
        raise ValueError("Selected band has no valid pixels")
    return band, valid_mask


def _read_stack(src: rasterio.DatasetReader) -> tuple[np.ndarray, np.ndarray]:
    data = src.read(masked=True).astype("float32")
    stack = np.asarray(data.filled(np.nan), dtype="float32")
    valid_mask = ~np.any(np.ma.getmaskarray(data), axis=0) & np.all(np.isfinite(stack), axis=0)
    if src.count < 2:
        raise ValueError("PCA requires a raster with at least two bands")
    if not np.any(valid_mask):
        raise ValueError("Raster has no pixels valid across all bands")
    return stack, valid_mask


def _fill_invalid(data: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    filled = np.asarray(data, dtype="float32").copy()
    mean_value = float(np.nanmean(filled[valid_mask]))
    if not math.isfinite(mean_value):
        mean_value = 0.0
    filled[~valid_mask] = mean_value
    return filled


def _fourier(data: np.ndarray, valid_mask: np.ndarray, output: FourierOutput) -> np.ndarray:
    filled = _fill_invalid(data, valid_mask)
    spectrum = np.fft.fftshift(np.fft.fft2(filled))
    if output == "phase":
        result = np.angle(spectrum)
    else:
        magnitude = np.abs(spectrum)
        if output == "power":
            result = np.log1p(magnitude * magnitude)
        else:
            result = np.log1p(magnitude)
    return np.asarray(result, dtype="float32")


def _wavelet(
    data: np.ndarray,
    valid_mask: np.ndarray,
    output: WaveletOutput,
    level: int,
) -> np.ndarray:
    try:
        levels = int(level)
    except (TypeError, ValueError) as exc:
        raise ValueError("wavelet_level must be an integer") from exc
    if levels < 1:
        raise ValueError("wavelet_level must be at least 1")

    original_shape = data.shape
    current = _fill_invalid(data, valid_mask)
    coeffs = None
    for _ in range(levels):
        current, horizontal, vertical, diagonal = _haar_step(current)
        coeffs = (current, horizontal, vertical, diagonal)
        if min(current.shape) < 2:
            break

    if coeffs is None:
        raise ValueError("Wavelet transform could not be computed")

    approximation, horizontal, vertical, diagonal = coeffs
    if output == "approximation":
        selected = approximation
    elif output == "horizontal":
        selected = horizontal
    elif output == "vertical":
        selected = vertical
    elif output == "diagonal":
        selected = diagonal
    else:
        selected = np.sqrt(horizontal * horizontal + vertical * vertical + diagonal * diagonal)

    return _upsample_to_shape(selected, original_shape).astype("float32")


def _haar_step(data: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    padded = _pad_even(data)
    even_rows = padded[0::2, :]
    odd_rows = padded[1::2, :]
    low_rows = (even_rows + odd_rows) / 2.0
    high_rows = (even_rows - odd_rows) / 2.0

    even_low = low_rows[:, 0::2]
    odd_low = low_rows[:, 1::2]
    even_high = high_rows[:, 0::2]
    odd_high = high_rows[:, 1::2]

    approximation = (even_low + odd_low) / 2.0
    horizontal = (even_low - odd_low) / 2.0
    vertical = (even_high + odd_high) / 2.0
    diagonal = (even_high - odd_high) / 2.0
    return approximation, horizontal, vertical, diagonal


def _pad_even(data: np.ndarray) -> np.ndarray:
    rows, cols = data.shape
    pad_rows = rows % 2
    pad_cols = cols % 2
    if pad_rows == 0 and pad_cols == 0:
        return data
    return np.pad(data, ((0, pad_rows), (0, pad_cols)), mode="edge")


def _upsample_to_shape(data: np.ndarray, shape: tuple[int, int]) -> np.ndarray:
    row_factor = max(1, int(math.ceil(shape[0] / data.shape[0])))
    col_factor = max(1, int(math.ceil(shape[1] / data.shape[1])))
    upsampled = np.repeat(np.repeat(data, row_factor, axis=0), col_factor, axis=1)
    return upsampled[: shape[0], : shape[1]]


def _pca(
    stack: np.ndarray,
    valid_mask: np.ndarray,
    component_count: int,
    standardize: bool,
) -> tuple[np.ndarray, list[str], dict[str, Any]]:
    bands, height, width = stack.shape
    try:
        requested_components = int(component_count)
    except (TypeError, ValueError) as exc:
        raise ValueError("pca_components must be an integer") from exc
    if requested_components < 1:
        raise ValueError("pca_components must be at least 1")
    components = min(requested_components, bands)

    samples = stack[:, valid_mask].T.astype("float64")
    if samples.shape[0] < 2:
        raise ValueError("PCA requires at least two valid pixels")
    means = samples.mean(axis=0)
    centered = samples - means
    scales = np.ones(bands, dtype="float64")
    if standardize:
        scales = samples.std(axis=0)
        scales[scales <= 1e-12] = 1.0
        centered = centered / scales

    covariance = np.cov(centered, rowvar=False)
    eigenvalues, eigenvectors = np.linalg.eigh(covariance)
    order = np.argsort(eigenvalues)[::-1]
    eigenvalues = np.maximum(eigenvalues[order], 0.0)
    eigenvectors = eigenvectors[:, order]

    selected_vectors = eigenvectors[:, :components]
    projected = centered @ selected_vectors
    output = np.full((components, height, width), np.nan, dtype="float32")
    for component_index in range(components):
        output[component_index, valid_mask] = projected[:, component_index].astype("float32")

    total_variance = float(eigenvalues.sum())
    explained = eigenvalues[:components] / total_variance if total_variance > 0 else np.zeros(components)
    descriptions = [f"PCA component {index + 1}" for index in range(components)]
    return output, descriptions, {
        "pca_components": int(components),
        "pca_standardize": bool(standardize),
        "explained_variance_ratio": [float(value) for value in explained],
        "band_means": [float(value) for value in means],
        "band_scales": [float(value) for value in scales],
    }


def _prepare_float_output(stack: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    output = np.asarray(stack, dtype="float32").copy()
    output[:, ~valid_mask] = _FLOAT_NODATA
    output[~np.isfinite(output)] = _FLOAT_NODATA
    return output


def _write_stack(
    output_path: str,
    profile: dict[str, Any],
    stack: np.ndarray,
    descriptions: list[str],
) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    profile.update(
        driver="GTiff",
        count=int(stack.shape[0]),
        dtype="float32",
        nodata=_FLOAT_NODATA,
        compress="lzw",
    )
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(stack.astype("float32"))
        for band_index, description in enumerate(descriptions, start=1):
            dst.set_band_description(band_index, description)
        dst.update_tags(RASTER_TRANSFORM_ANALYSIS="true")
