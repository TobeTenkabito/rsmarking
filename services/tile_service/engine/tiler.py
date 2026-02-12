import numpy as np
import rasterio
import mercantile
import os
import traceback
from rasterio.windows import from_bounds
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds
from pyproj import Transformer

# Try to import the highly optimized Cython implementation
try:
    from .rendering import render_tile

    HAS_FAST_TILER = True
except (ImportError, ValueError):
    HAS_FAST_TILER = False
    print("### [INFO] Cython fast_tiler not found, using optimized NumPy engine. ###")

try:
    from .translator import fast_stretch_and_stack
except (ImportError, ValueError):
    try:
        import translator

        fast_stretch_and_stack = translator.fast_stretch_and_stack
    except ImportError:
        fast_stretch_and_stack = None


class TileEngine:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._src = None
        self._stats_cache = {}
        self._transformer = None
        self._crs_wgs84 = 'EPSG:4326'

    def _get_src(self):
        """Ensure file handle and transformer reuse throughout the instance lifecycle"""
        if self._src is None or self._src.closed:
            self._src = rasterio.open(self.file_path)
            self._transformer = Transformer.from_crs(self._crs_wgs84, self._src.crs, always_xy=True)
        return self._src

    def read_tile(self, x: int, y: int, z: int, bands: list = None, stats: dict = None):
        if not os.path.exists(self.file_path):
            return None

        try:
            src = self._get_src()

            if bands:
                valid_bands = [b for b in bands if 1 <= b <= src.count]
            else:
                valid_bands = list(range(1, min(4, src.count) + 1))

            if not valid_bands:
                valid_bands = [1]

            # Coordinate transformation using cached transformer
            tile_wgs84 = mercantile.bounds(x, y, z)
            left, bottom = self._transformer.transform(tile_wgs84.west, tile_wgs84.south)
            right, top = self._transformer.transform(tile_wgs84.east, tile_wgs84.north)

            window = from_bounds(left, bottom, right, top, transform=src.transform)

            # Optimized read into target shape
            data = src.read(
                valid_bands,
                window=window,
                out_shape=(len(valid_bands), 256, 256),
                resampling=Resampling.bilinear,
                boundless=True,
                fill_value=0
            ).astype(np.float32)

            if not np.any(data):
                return None

            mins = []
            maxs = []

            for i, b_idx in enumerate(valid_bands):
                b_str = str(b_idx)

                if stats and b_str in stats:
                    mins.append(stats[b_str].get('low', 0))
                    maxs.append(stats[b_str].get('high', 1000))
                elif b_idx in self._stats_cache:
                    s = self._stats_cache[b_idx]
                    mins.append(s[0])
                    maxs.append(s[1])
                else:
                    b_meta = src.tags(b_idx)
                    m_min = b_meta.get('STATISTICS_MINIMUM')
                    m_max = b_meta.get('STATISTICS_MAXIMUM')

                    if m_min is not None and m_max is not None:
                        val = (float(m_min), float(m_max))
                        self._stats_cache[b_idx] = val
                        mins.append(val[0])
                        maxs.append(val[1])
                    else:
                        # Fast sampling for percentile calculation
                        valid_mask = data[i] > 0
                        valid_data = data[i][valid_mask]
                        if valid_data.size > 500:
                            sample = valid_data[::10]
                            low = np.percentile(sample, 2)
                            high = np.percentile(sample, 98)
                            mins.append(low)
                            maxs.append(high)
                        elif valid_data.size > 0:
                            mins.append(np.min(valid_data))
                            maxs.append(np.max(valid_data))
                        else:
                            mins.append(0)
                            maxs.append(1)

            mins = np.array(mins, dtype=np.float32)
            maxs = np.array(maxs, dtype=np.float32)

            # Execution Priority: 1. fast_tiler (.pyx) -> 2. translator (Cython) -> 3. NumPy (Fallback)
            if HAS_FAST_TILER:
                return render_tile(data, mins, maxs)

            if fast_stretch_and_stack:
                return fast_stretch_and_stack(data, mins, maxs)
            else:
                return self._fallback_process(data, mins, maxs)

        except Exception as e:
            print(f"### [TILE_ENGINE_ERROR] {e} ###")
            return None

    def _fallback_process(self, data, mins, maxs):
        """
        Pure NumPy vectorized implementation (highly optimized fallback)
        """
        mins_v = mins.reshape(-1, 1, 1)
        maxs_v = maxs.reshape(-1, 1, 1)

        ranges = maxs_v - mins_v
        safe_ranges = np.where(ranges <= 0, 1.0, ranges)

        stretched = (data - mins_v) / safe_ranges * 255
        processed = np.clip(stretched, 0, 255).astype(np.uint8)

        count, h, w = data.shape

        if count == 1:
            rgb = np.repeat(processed, 3, axis=0)
        elif count == 2:
            padding = np.zeros((1, h, w), dtype=np.uint8)
            rgb = np.concatenate([processed, padding], axis=0)
        else:
            rgb = processed[:3]

        alpha = (np.any(data > 0, axis=0)).astype(np.uint8) * 255

        return np.dstack([rgb.transpose(1, 2, 0), alpha])

    def __del__(self):
        if hasattr(self, '_src') and self._src:
            self._src.close()
