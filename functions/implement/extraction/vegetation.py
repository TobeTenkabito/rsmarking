import numpy as np
from ..spectral_indices import calculate_ndvi_array


def extract_vegetation(bands: list[np.ndarray], threshold: float, mode: str = "ndvi") -> np.ndarray:
    mode = mode.lower() if mode else "ndvi"

    if mode == "ndvi" or len(bands) >= 2:
        red, nir = bands[0], bands[1]
        ndvi = calculate_ndvi_array(red, nir)
        return (ndvi > threshold).astype('uint8')
    else:
<<<<<<< HEAD
        raise ValueError(f"Unknown vegetation extraction mode or insufficient bands: {mode}")
=======
        raise ValueError(f"Unknown vegetation extraction mode or insufficient bands: {mode}")
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
