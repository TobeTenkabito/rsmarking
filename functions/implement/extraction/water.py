import numpy as np
from ..spectral_indices import calculate_mndwi_array, calculate_ndwi_array
from .water_utils import(
    GeoAdaptive,
    jrc_water,
    compute_otsu_threshold
)


def extract_water(bands: list[np.ndarray], threshold: float, mode: str = "mndwi") -> np.ndarray:
    mode = mode.lower() if mode else "mndwi"

    if mode == "mndwi":
        if len(bands) < 2: raise ValueError("MNDWI requires 2 bands")
        green, swir = bands[0], bands[1]
        mndwi = calculate_mndwi_array(green, swir)
        return (mndwi > threshold).astype('uint8')

    elif mode == "ndwi":
        if len(bands) < 2: raise ValueError("NDWI requires 2 bands")
        green, swir = bands[0], bands[1]
        ndwi = calculate_ndwi_array(green, swir)
        return (ndwi > threshold).astype('uint8')

    elif mode.startswith("jrc"):
        return jrc_water(bands, threshold, mode.replace("jrc_", ""))

    elif mode == "otsu":
        if len(bands) < 2:
            raise ValueError("Otsu extraction (MNDWI-based) requires Green and SWIR bands")
        green, swir = bands[0], bands[1]
        mndwi = calculate_mndwi_array(green, swir)
        dynamic_thresh = compute_otsu_threshold(mndwi)
        return (mndwi > dynamic_thresh).astype('uint8')

    elif mode == "awei":
        if len(bands) < 5:
            raise ValueError("AWEI extraction needs 5 bands at least")
        b, g, r, nir, sw1, sw2 = bands[0], bands[1], bands[2], bands[3], bands[4], bands[5]
        awei = 4 * (g - sw1) - (0.25 * nir + 2.75 * sw2)
        return (awei > threshold).astype("uint8")

    elif mode == "ga":
        engine = GeoAdaptive(chunk_size=50000)
        return engine.process(bands, threshold)

    else:
        raise ValueError(f"Unknown water extraction mode: {mode}")
