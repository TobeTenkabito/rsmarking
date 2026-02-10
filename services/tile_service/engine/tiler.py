import numpy as np
import rasterio
import mercantile
import os
import traceback
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds

try:
    from .translator import fast_stretch_and_stack
except (ImportError, ValueError):
    try:
        import translator

        fast_stretch_and_stack = translator.fast_stretch_and_stack
    except ImportError:
        fast_stretch_and_stack = None
        print("### [WARNING] Cython module not found, using fallback. ###")


class TileEngine:
    def __init__(self, file_path: str):
        self.file_path = file_path

    def read_tile(self, x: int, y: int, z: int, bands: list = None, stats: dict = None):
        if not os.path.exists(self.file_path):
            return None

        try:
            with rasterio.open(self.file_path) as src:
                if bands:
                    valid_bands = [b for b in bands if 1 <= b <= src.count]
                else:
                    valid_bands = list(range(1, min(4, src.count) + 1))
                if not valid_bands:
                    valid_bands = [1]
                tile_wgs84 = mercantile.bounds(x, y, z)
                left, bottom, right, top = transform_bounds(
                    'EPSG:4326', src.crs,
                    tile_wgs84.west, tile_wgs84.south, tile_wgs84.east, tile_wgs84.north
                )
                window = from_bounds(left, bottom, right, top, transform=src.transform)
                data = src.read(
                    valid_bands,
                    window=window,
                    out_shape=(len(valid_bands), 256, 256),
                    resampling=Resampling.bilinear,
                    boundless=True,
                    fill_value=0
                ).astype(np.float32)
                if np.max(data) <= 0:
                    return None

                mins = []
                maxs = []

                for i, b_idx in enumerate(valid_bands):
                    b_str = str(b_idx)

                    if stats and b_str in stats:
                        mins.append(stats[b_str].get('low', 0))
                        maxs.append(stats[b_str].get('high', 1000))
                    else:
                        b_meta = src.tags(b_idx)
                        m_min = b_meta.get('STATISTICS_MINIMUM')
                        m_max = b_meta.get('STATISTICS_MAXIMUM')

                        if m_min is not None and m_max is not None:
                            mins.append(float(m_min))
                            maxs.append(float(m_max))
                        else:
                            valid_mask = data[i] > 0
                            if np.any(valid_mask):
                                mins.append(np.percentile(data[i][valid_mask], 1))
                                maxs.append(np.percentile(data[i][valid_mask], 99))
                            else:
                                mins.append(0)
                                maxs.append(1)

                mins = np.array(mins, dtype=np.float32)
                maxs = np.array(maxs, dtype=np.float32)

                if fast_stretch_and_stack:
                    return fast_stretch_and_stack(data, mins, maxs)
                else:
                    return self._fallback_process(data, mins, maxs)

        except Exception as e:
            print(f"### [TILE_ENGINE_ERROR] {e} ###")
            traceback.print_exc()
            return None

    def _fallback_process(self, data, mins, maxs):
        count, h, w = data.shape
        processed = []

        for i in range(count):
            low, high = mins[i], maxs[i]
            rng = high - low
            if rng <= 0: rng = 1.0

            s = (data[i] - low) / rng * 255
            processed.append(np.clip(s, 0, 255).astype(np.uint8))

        if len(processed) == 1:
            rgb = np.stack([processed[0]] * 3, axis=-1)
        elif len(processed) == 2:
            rgb = np.stack([processed[0], processed[1], np.zeros((h, w), dtype=np.uint8)], axis=-1)
        else:
            rgb = np.stack(processed[:3], axis=-1)

        alpha = (np.max(data, axis=0) > 0).astype(np.uint8) * 255
        return np.dstack([rgb, alpha])
