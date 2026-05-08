import numpy as np
from .cloud_utils import (
    CloudParams,
    cirrus_cloud,
    cloud_score_mask,
    fmask_cloud,
    threshold_cloud,
)


def extract_cloud(
    bands: list[np.ndarray],
    threshold: float | None = None,
    mode: str = "default",
) -> np.ndarray:
    if isinstance(threshold, str):
        try:
            threshold = float(threshold)
        except ValueError:
            mode = threshold
            threshold = None

    mode = mode.lower() if mode else "default"

    if mode in {"default", "threshold", "simple", "blue_swir"}:
        params = CloudParams(
            blue_threshold=0.40,
            swir_threshold=0.0,
            min_component_size=1,
            apply_morphology=False,
        )
        return threshold_cloud(bands, threshold, params)

    if mode in {"score", "prob", "probability"}:
        score_threshold = threshold if threshold and threshold > 0 else None
        return cloud_score_mask(bands, score_threshold)

    if mode in {"fmask", "fmask_standard"}:
        score_threshold = threshold if threshold and threshold > 0 else None
        return fmask_cloud(bands, score_threshold)

    if mode == "fmask_strict":
        params = CloudParams(
            blue_threshold=0.30,
            swir_threshold=0.22,
            brightness_threshold=0.35,
            whiteness_max=0.55,
            score_threshold=0.65,
        )
        score_threshold = threshold if threshold and threshold > 0 else None
        return fmask_cloud(bands, score_threshold, params)

    if mode in {"fmask_sensitive", "sensitive"}:
        params = CloudParams(
            blue_threshold=0.18,
            swir_threshold=0.12,
            brightness_threshold=0.22,
            whiteness_max=0.85,
            score_threshold=0.45,
            min_component_size=4,
        )
        score_threshold = threshold if threshold and threshold > 0 else None
        return fmask_cloud(bands, score_threshold, params)

    if mode == "cirrus":
        return cirrus_cloud(bands, threshold)

    raise ValueError(f"Unknown cloud extraction mode: {mode}")
