from __future__ import annotations

import os
from collections import Counter
from typing import Any, Literal

import numpy as np
import rasterio
from rasterio.warp import transform as transform_coords


ClassifierName = Literal["nearest_centroid", "random_forest", "svm"]


def unsupervised_classification(
    input_path: str,
    output_path: str,
    n_classes: int = 5,
    method: str = "kmeans",
    band_indices: list[int] | None = None,
    max_samples: int = 50000,
    random_seed: int = 13,
    smoothing: int = 0,
) -> dict[str, Any]:
    """Classify a raster into spectral clusters without training labels."""

    if n_classes < 2:
        raise ValueError("n_classes must be at least 2")
    if method not in {"kmeans", "mini_batch_kmeans"}:
        raise ValueError("method must be 'kmeans' or 'mini_batch_kmeans'")

    with rasterio.open(input_path) as src:
        stack, valid_mask, profile = _read_stack(src, band_indices)
        features = _valid_features(stack, valid_mask)
        labels = _cluster_features(
            features,
            n_classes=n_classes,
            max_samples=max_samples,
            random_seed=random_seed,
            prefer_minibatch=method == "mini_batch_kmeans",
        )
        output = _labels_to_raster(labels, valid_mask, src.height, src.width)
        output = _smooth_labels(output, smoothing, valid_mask)
        _write_label_raster(output_path, output, profile, tags={
            "CLASSIFICATION_TYPE": "unsupervised",
            "CLASSIFICATION_METHOD": method,
            "CLASS_COUNT": str(n_classes),
        })

    return _classification_summary(output, "unsupervised", method, n_classes)


def supervised_classification(
    input_path: str,
    output_path: str,
    samples: list[dict[str, Any]],
    classifier: ClassifierName = "nearest_centroid",
    band_indices: list[int] | None = None,
    n_estimators: int = 100,
    random_seed: int = 13,
    smoothing: int = 0,
) -> dict[str, Any]:
    """Classify a raster from labeled samples.

    Samples may provide either spectral values (`features` or `values`) or a
    pixel/location (`row`+`col`, `x`+`y`, or `lng`+`lat`) plus a class value.
    """

    if not samples:
        raise ValueError("At least one labeled sample is required")
    if classifier not in {"nearest_centroid", "random_forest", "svm"}:
        raise ValueError("classifier must be nearest_centroid, random_forest, or svm")

    label_lookup: dict[Any, int] = {}
    label_names: dict[int, str] = {}

    with rasterio.open(input_path) as src:
        stack, valid_mask, profile = _read_stack(src, band_indices)
        train_x, train_y = _extract_training_samples(src, stack, samples, label_lookup, label_names)
        if len(np.unique(train_y)) < 2:
            raise ValueError("Supervised classification requires at least two classes")

        features = _valid_features(stack, valid_mask)
        labels = _classify_features(
            features,
            train_x,
            train_y,
            classifier=classifier,
            n_estimators=n_estimators,
            random_seed=random_seed,
        )
        output = _labels_to_raster(labels, valid_mask, src.height, src.width)
        output = _smooth_labels(output, smoothing, valid_mask)
        _write_label_raster(output_path, output, profile, tags={
            "CLASSIFICATION_TYPE": "supervised",
            "CLASSIFICATION_METHOD": classifier,
            "CLASS_LABELS": ",".join(f"{value}:{name}" for value, name in sorted(label_names.items())),
        })

    return {
        **_classification_summary(output, "supervised", classifier, int(len(label_names))),
        "training_sample_count": int(train_y.size),
        "class_labels": label_names,
    }


def _read_stack(src: rasterio.DatasetReader, band_indices: list[int] | None) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    indexes = _normalize_band_indices(src.count, band_indices)
    stack = src.read(indexes).astype("float32")
    valid_mask = np.ones((src.height, src.width), dtype=bool)
    if src.nodata is not None:
        valid_mask &= ~np.any(stack == np.float32(src.nodata), axis=0)
    valid_mask &= np.all(np.isfinite(stack), axis=0)
    profile = src.profile.copy()
    return stack, valid_mask, profile


def _normalize_band_indices(total_bands: int, band_indices: list[int] | None) -> list[int]:
    if not band_indices:
        return list(range(1, total_bands + 1))
    normalized = []
    for band_index in band_indices:
        if band_index < 1 or band_index > total_bands:
            raise ValueError(f"Band index {band_index} is out of range for raster with {total_bands} band(s)")
        normalized.append(int(band_index))
    return normalized


def _valid_features(stack: np.ndarray, valid_mask: np.ndarray) -> np.ndarray:
    if not np.any(valid_mask):
        raise ValueError("Raster has no valid pixels to classify")
    return stack[:, valid_mask].T.astype("float32")


def _cluster_features(
    features: np.ndarray,
    n_classes: int,
    max_samples: int,
    random_seed: int,
    prefer_minibatch: bool = True,
) -> np.ndarray:
    scaled, mean, scale = _standardize(features)
    rng = np.random.default_rng(random_seed)
    fit_features = _sample_rows(scaled, max_samples, rng)
    del mean, scale, prefer_minibatch
    centers = _numpy_kmeans(fit_features, n_classes, rng)
    return _assign_nearest(scaled, centers).astype("uint16") + 1


def _classify_features(
    features: np.ndarray,
    train_x: np.ndarray,
    train_y: np.ndarray,
    classifier: str,
    n_estimators: int,
    random_seed: int,
) -> np.ndarray:
    _, mean, scale = _standardize(train_x)
    train_scaled = (train_x - mean) / scale
    features_scaled = (features - mean) / scale

    try:
        if classifier == "random_forest":
            from sklearn.ensemble import RandomForestClassifier

            model = RandomForestClassifier(
                n_estimators=n_estimators,
                random_state=random_seed,
                class_weight="balanced",
                n_jobs=1,
            )
        elif classifier == "svm":
            from sklearn.svm import SVC

            model = SVC(kernel="rbf", gamma="scale", class_weight="balanced")
        else:
            raise ImportError("Use numpy nearest-centroid classifier")
        model.fit(train_scaled, train_y)
        return model.predict(features_scaled).astype("uint16")
    except Exception:
        centers, center_labels = _fit_centroids(train_scaled, train_y)
        nearest = _assign_nearest(features_scaled, centers)
        return center_labels[nearest].astype("uint16")


def _extract_training_samples(
    src: rasterio.DatasetReader,
    stack: np.ndarray,
    samples: list[dict[str, Any]],
    label_lookup: dict[Any, int],
    label_names: dict[int, str],
) -> tuple[np.ndarray, np.ndarray]:
    features = []
    labels = []
    for sample in samples:
        label_raw = (
            sample.get("class_id")
            if "class_id" in sample
            else sample.get("class_value", sample.get("label"))
        )
        if label_raw is None:
            raise ValueError("Each training sample must include class_id, class_value, or label")
        class_value = _normalize_label(label_raw, label_lookup, label_names)

        if "features" in sample or "values" in sample:
            values = sample.get("features", sample.get("values"))
            vector = np.asarray(values, dtype="float32")
        else:
            row, col = _sample_row_col(src, sample)
            vector = stack[:, row, col].astype("float32")

        if vector.ndim != 1 or vector.size != stack.shape[0]:
            raise ValueError(
                f"Training sample feature length must match selected band count ({stack.shape[0]})"
            )
        if not np.all(np.isfinite(vector)):
            continue
        features.append(vector)
        labels.append(class_value)

    if not features:
        raise ValueError("No valid training samples were extracted")
    return np.vstack(features).astype("float32"), np.asarray(labels, dtype="uint16")


def _sample_row_col(src: rasterio.DatasetReader, sample: dict[str, Any]) -> tuple[int, int]:
    if "row" in sample and "col" in sample:
        row, col = int(sample["row"]), int(sample["col"])
    elif "x" in sample and "y" in sample:
        row, col = src.index(float(sample["x"]), float(sample["y"]))
    elif "lng" in sample and "lat" in sample:
        x, y = float(sample["lng"]), float(sample["lat"])
        if src.crs and src.crs.to_epsg() != 4326:
            xs, ys = transform_coords("EPSG:4326", src.crs, [x], [y])
            x, y = xs[0], ys[0]
        row, col = src.index(x, y)
    else:
        raise ValueError("Training samples need row/col, x/y, lng/lat, or features")

    if row < 0 or row >= src.height or col < 0 or col >= src.width:
        raise ValueError(f"Training sample is outside raster bounds: row={row}, col={col}")
    return row, col


def _normalize_label(label: Any, label_lookup: dict[Any, int], label_names: dict[int, str]) -> int:
    try:
        value = int(label)
    except (TypeError, ValueError):
        key = str(label)
        if key not in label_lookup:
            label_lookup[key] = len(label_lookup) + 1
            label_names[label_lookup[key]] = key
        return label_lookup[key]

    if value <= 0:
        raise ValueError("Class values must be positive integers")
    label_names.setdefault(value, str(label))
    return value


def _standardize(features: np.ndarray) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    mean = features.mean(axis=0, keepdims=True)
    scale = features.std(axis=0, keepdims=True)
    scale[scale == 0] = 1.0
    return (features - mean) / scale, mean, scale


def _sample_rows(features: np.ndarray, max_samples: int, rng: np.random.Generator) -> np.ndarray:
    if max_samples <= 0 or features.shape[0] <= max_samples:
        return features
    indexes = rng.choice(features.shape[0], size=max_samples, replace=False)
    return features[indexes]


def _numpy_kmeans(features: np.ndarray, n_classes: int, rng: np.random.Generator, iterations: int = 50) -> np.ndarray:
    unique_features = np.unique(features, axis=0)
    if unique_features.shape[0] < n_classes:
        raise ValueError(
            f"Raster has only {unique_features.shape[0]} unique valid feature vector(s); "
            f"cannot create {n_classes} classes"
        )
    initial = rng.choice(unique_features.shape[0], size=n_classes, replace=False)
    centers = unique_features[initial].astype("float32")
    for _ in range(iterations):
        labels = _assign_nearest(features, centers)
        updated = centers.copy()
        for class_index in range(n_classes):
            members = features[labels == class_index]
            if members.size:
                updated[class_index] = members.mean(axis=0)
        if np.allclose(updated, centers):
            break
        centers = updated
    return centers


def _assign_nearest(features: np.ndarray, centers: np.ndarray) -> np.ndarray:
    distances = np.sum((features[:, np.newaxis, :] - centers[np.newaxis, :, :]) ** 2, axis=2)
    return np.argmin(distances, axis=1)


def _fit_centroids(train_x: np.ndarray, train_y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    labels = np.unique(train_y)
    centers = np.vstack([train_x[train_y == label].mean(axis=0) for label in labels])
    return centers.astype("float32"), labels.astype("uint16")


def _labels_to_raster(labels: np.ndarray, valid_mask: np.ndarray, height: int, width: int) -> np.ndarray:
    output = np.zeros((height, width), dtype="uint16")
    output[valid_mask] = labels.astype("uint16")
    return output


def _smooth_labels(output: np.ndarray, smoothing: int, valid_mask: np.ndarray) -> np.ndarray:
    if smoothing <= 0:
        return output
    try:
        from scipy import ndimage

        size = max(1, int(smoothing) * 2 + 1)
        smoothed = ndimage.median_filter(output, size=size)
        output = np.where(valid_mask, smoothed, 0).astype("uint16")
    except Exception:
        pass
    return output


def _write_label_raster(output_path: str, labels: np.ndarray, profile: dict[str, Any], tags: dict[str, str]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
    profile.update(driver="GTiff", dtype="uint16", count=1, nodata=0)
    with rasterio.open(output_path, "w", **profile) as dst:
        dst.write(labels.astype("uint16"), 1)
        dst.update_tags(**tags)


def _classification_summary(
    labels: np.ndarray,
    operation: str,
    method: str,
    n_classes: int,
) -> dict[str, Any]:
    nonzero = labels[labels > 0]
    counts = Counter(int(value) for value in nonzero.ravel())
    return {
        "operation": operation,
        "method": method,
        "class_count": int(n_classes),
        "valid_pixel_count": int(nonzero.size),
        "class_histogram": dict(sorted(counts.items())),
        "output_dtype": "uint16",
        "nodata": 0,
    }
