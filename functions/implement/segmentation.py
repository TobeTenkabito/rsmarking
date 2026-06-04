from __future__ import annotations

import os
from typing import Any, Literal

import numpy as np
import rasterio

from functions.implement.classification import (
    _classification_summary,
    _cluster_features,
    _labels_to_raster,
    _read_stack,
    _smooth_labels,
    _valid_features,
    _write_label_raster,
)


SegmentationBackend = Literal["auto", "onnx", "spectral_spatial", "slic", "watershed"]


def deep_learning_segmentation(
    input_path: str,
    output_path: str,
    model_path: str | None = None,
    backend: SegmentationBackend = "auto",
    n_classes: int = 2,
    band_indices: list[int] | None = None,
    threshold: float = 0.5,
    random_seed: int = 13,
    max_samples: int = 50000,
    compactness: float = 0.15,
    smoothing: int = 1,
) -> dict[str, Any]:
    """Run a segmentation module with optional ONNX model support.

    When `model_path` is omitted, the built-in spectral-spatial backend creates
    an edge-aware segmentation using normalized spectral features and pixel
    coordinates. This keeps the module usable without downloading a model while
    preserving the same API for future trained model backends.
    """

    if n_classes < 2:
        raise ValueError("n_classes must be at least 2")
    if backend not in {"auto", "onnx", "spectral_spatial", "slic", "watershed"}:
        raise ValueError("backend must be auto, onnx, spectral_spatial, slic, or watershed")

    with rasterio.open(input_path) as src:
        stack, valid_mask, profile = _read_stack(src, band_indices)
        chosen_backend = "onnx" if model_path and backend in {"auto", "onnx"} else backend
        if chosen_backend == "auto":
            chosen_backend = "spectral_spatial"

        if chosen_backend == "onnx":
            output = _run_onnx_segmentation(
                stack,
                valid_mask,
                model_path=model_path,
                threshold=threshold,
                target_shape=(src.height, src.width),
            )
        else:
            output = _spectral_spatial_segmentation(
                stack,
                valid_mask,
                n_classes=n_classes,
                max_samples=max_samples,
                random_seed=random_seed,
                compactness=compactness,
                smoothing=smoothing,
            )

        _write_label_raster(output_path, output, profile, tags={
            "SEGMENTATION_TYPE": "deep_learning",
            "SEGMENTATION_BACKEND": chosen_backend,
            "CLASS_COUNT": str(int(output.max())),
            "MODEL_PATH": model_path or "",
        })

    return _classification_summary(output, "deep_learning_segmentation", chosen_backend, int(output.max()))


def _spectral_spatial_segmentation(
    stack: np.ndarray,
    valid_mask: np.ndarray,
    n_classes: int,
    max_samples: int,
    random_seed: int,
    compactness: float,
    smoothing: int,
) -> np.ndarray:
    normalized = _normalize_stack(stack, valid_mask)
    intensity = normalized.mean(axis=0)
    rows, cols = np.indices(valid_mask.shape, dtype="float32")
    if rows.shape[0] > 1:
        rows /= rows.shape[0] - 1
    if cols.shape[1] > 1:
        cols /= cols.shape[1] - 1

    edge = _gradient_magnitude(intensity)
    feature_stack = np.concatenate(
        [
            normalized,
            (rows[np.newaxis, ...] * float(compactness)).astype("float32"),
            (cols[np.newaxis, ...] * float(compactness)).astype("float32"),
            edge[np.newaxis, ...].astype("float32"),
        ],
        axis=0,
    )
    features = _valid_features(feature_stack, valid_mask)
    labels = _cluster_features(
        features,
        n_classes=n_classes,
        max_samples=max_samples,
        random_seed=random_seed,
        prefer_minibatch=True,
    )
    output = _labels_to_raster(labels, valid_mask, valid_mask.shape[0], valid_mask.shape[1])
    return _smooth_labels(output, smoothing, valid_mask)


def _run_onnx_segmentation(
    stack: np.ndarray,
    valid_mask: np.ndarray,
    model_path: str | None,
    threshold: float,
    target_shape: tuple[int, int],
) -> np.ndarray:
    if not model_path:
        raise ValueError("model_path is required for the onnx segmentation backend")
    if not os.path.exists(model_path):
        raise ValueError(f"ONNX model was not found: {model_path}")

    try:
        import onnxruntime as ort
    except Exception as exc:
        raise ValueError("onnxruntime is required for the onnx segmentation backend") from exc

    normalized = _normalize_stack(stack, valid_mask)
    tensor = normalized[np.newaxis, ...].astype("float32")
    session = ort.InferenceSession(model_path, providers=["CPUExecutionProvider"])
    input_name = session.get_inputs()[0].name
    output = session.run(None, {input_name: tensor})[0]
    labels = _onnx_output_to_labels(output, threshold, target_shape)
    labels[~valid_mask] = 0
    return labels.astype("uint16")


def _onnx_output_to_labels(output: np.ndarray, threshold: float, target_shape: tuple[int, int]) -> np.ndarray:
    arr = np.asarray(output)
    if arr.ndim == 4:
        arr = arr[0]
    if arr.ndim == 3:
        if arr.shape[0] == 1:
            arr = (arr[0] >= threshold).astype("uint16") + 1
        else:
            arr = np.argmax(arr, axis=0).astype("uint16") + 1
    elif arr.ndim == 2:
        arr = arr.astype("uint16")
        if arr.max(initial=0) == 1:
            arr = arr + 1
    else:
        raise ValueError(f"Unsupported ONNX segmentation output shape: {arr.shape}")

    if arr.shape != target_shape:
        try:
            from scipy import ndimage

            factors = (target_shape[0] / arr.shape[0], target_shape[1] / arr.shape[1])
            arr = ndimage.zoom(arr, factors, order=0)
        except Exception as exc:
            raise ValueError(
                f"ONNX output shape {arr.shape} does not match raster shape {target_shape}"
            ) from exc
    return arr.astype("uint16")


def _normalize_stack(stack: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    normalized = np.zeros_like(stack, dtype="float32")
    for idx in range(stack.shape[0]):
        band = stack[idx]
        valid = band[valid_mask]
        if valid.size == 0:
            continue
        low, high = np.percentile(valid, [2, 98])
        if high <= low:
            high = low + 1.0
        normalized[idx] = np.clip((band - low) / (high - low), 0.0, 1.0)
    return normalized


def _gradient_magnitude(intensity: np.ndarray) -> np.ndarray:
    gy, gx = np.gradient(intensity.astype("float32"))
    gradient = np.sqrt(gx * gx + gy * gy)
    maximum = float(np.nanmax(gradient)) if gradient.size else 0.0
    if maximum > 0:
        gradient = gradient / maximum
    return gradient.astype("float32")
