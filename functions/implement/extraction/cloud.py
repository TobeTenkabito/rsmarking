import numpy as np


def extract_cloud(bands: list[np.ndarray]) -> np.ndarray:
    if len(bands) < 1:
        raise ValueError("Cloud extraction requires at least 1 band (Blue)")

    blue = bands[0]
    cloud_mask = (blue > 0.4)
    if len(bands) >= 2:
        swir = bands[1]
        cloud_mask = cloud_mask & (swir > 0.3)

    return cloud_mask.astype('uint8')
