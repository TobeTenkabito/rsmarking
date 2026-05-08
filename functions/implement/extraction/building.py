import numpy as np
from .building_utils import (
    BuildingParams,
    building_score_mask,
    ibi_building,
    ndbi_building,
    urban_index_building,
)


def extract_building(
    bands: list[np.ndarray],
    threshold: float | None = None,
    mode: str = "ndbi",
) -> np.ndarray:
    if isinstance(threshold, str):
        try:
            threshold = float(threshold)
        except ValueError:
            mode = threshold
            threshold = None

    mode = mode.lower() if mode else "ndbi"

    if mode in {"default", "ndbi", "ndbi_ndvi"}:
        params = BuildingParams(
            min_component_size=1,
            apply_morphology=False,
        )
        return ndbi_building(bands, threshold, params)

    if mode == "ndbi_strict":
        params = BuildingParams(ndbi_threshold=0.08, ndvi_max=0.12, mndwi_max=-0.05)
        cutoff = threshold if threshold and threshold > 0 else None
        return ndbi_building(bands, cutoff, params)

    if mode in {"ndbi_sensitive", "sensitive"}:
        params = BuildingParams(
            ndbi_threshold=-0.05,
            ndvi_max=0.30,
            mndwi_max=0.10,
            min_component_size=4,
        )
        cutoff = threshold if threshold is not None else None
        return ndbi_building(bands, cutoff, params)

    if mode in {"ibi", "index_based"}:
        return ibi_building(bands, threshold)

    if mode == "ibi_strict":
        params = BuildingParams(ibi_threshold=0.08, ndvi_max=0.12, mndwi_max=-0.05)
        cutoff = threshold if threshold and threshold > 0 else None
        return ibi_building(bands, cutoff, params)

    if mode in {"ui", "urban_index"}:
        return urban_index_building(bands, threshold)

    if mode in {"score", "prob", "probability"}:
        cutoff = threshold if threshold and threshold > 0 else None
        return building_score_mask(bands, cutoff)

    raise ValueError(f"Unknown building extraction mode: {mode}")
