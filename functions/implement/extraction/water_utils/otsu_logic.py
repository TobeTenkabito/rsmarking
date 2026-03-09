import numpy as np


def compute_otsu_threshold(data: np.ndarray) -> float:
    mask = np.isfinite(data)
    valid_data = data[mask]

    if valid_data.size == 0:
        return 0.0
    return _pure_numpy_otsu_vectorized(valid_data)


def _pure_numpy_otsu_vectorized(valid_data: np.ndarray, bins: int = 256) -> float:
    hist, bin_edges = np.histogram(valid_data, bins=bins, range=(-1, 1))
    bin_centers = (bin_edges[:-1] + bin_edges[1:]) / 2
    weight1 = np.cumsum(hist)
    weight2 = np.cumsum(hist[::-1])[::-1]
    mean1 = np.cumsum(hist * bin_centers) / np.maximum(weight1, 1)
    mean2 = (np.cumsum((hist * bin_centers)[::-1]) / np.maximum(weight2[::-1], 1))[::-1]
    inter_class_variance = weight1[:-1] * weight2[1:] * (mean1[:-1] - mean2[1:]) ** 2
    max_idx = np.argmax(inter_class_variance)
    return float(bin_centers[max_idx])
