import numpy as np
import rasterio
import os
from pyproj import Transformer
from rasterio.enums import Resampling

from .stats import StatsManager
from .utils import get_tile_window


try:
    from .rendering import render_tile

    HAS_FAST_TILER = True
except (ImportError, ValueError):
    HAS_FAST_TILER = False

try:
    from .translator import fast_stretch_and_stack
except (ImportError, ValueError):
    fast_stretch_and_stack = None


class TileEngine:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self._src = None
        self._stats_manager = StatsManager()
        self._transformer = None
        self._crs_wgs84 = 'EPSG:4326'

    def _get_src(self):
        if self._src is None or self._src.closed:
            self._src = rasterio.open(self.file_path)
            self._transformer = Transformer.from_crs(self._crs_wgs84, self._src.crs, always_xy=True)
        return self._src

    def read_tile(self, x: int, y: int, z: int, bands: list = None, stats: dict = None):
        if not os.path.exists(self.file_path):
            return None
        try:
            src = self._get_src()
            valid_bands = bands if bands else list(range(1, min(4, src.count) + 1))
            valid_bands = [b for b in valid_bands if 1 <= b <= src.count] or [1]
            window = get_tile_window(x, y, z, src, self._transformer)
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
            d_min = np.min(data)
            d_max = np.max(data)
            num_bands = len(valid_bands)
            unique_values = np.unique(data)
            if len(unique_values) <= 2 and d_min >= 0 and d_max <= 1:
                mins = np.zeros(num_bands, dtype=np.float32)
                maxs = np.ones(num_bands, dtype=np.float32)
            elif d_min >= -1.0001 and d_max <= 1.0001:
                mins = np.full(num_bands, -1.0, dtype=np.float32)
                maxs = np.full(num_bands, 1.0, dtype=np.float32)
            else:
                mins, maxs = self._stats_manager.get_stretch_params(data, valid_bands, src, stats)
            if HAS_FAST_TILER:
                return render_tile(data, mins, maxs)
            if fast_stretch_and_stack:
                return fast_stretch_and_stack(data, mins, maxs)
            return self._fallback_process(data, mins, maxs)
        except Exception as e:
            print(f"### [TILE_ENGINE_ERROR] {e} ###")
            return None

    def _fallback_process(self, data, mins, maxs):
        mins_v, maxs_v = mins.reshape(-1, 1, 1), maxs.reshape(-1, 1, 1)
        ranges = np.where((maxs_v - mins_v) <= 0, 1.0, maxs_v - mins_v)
        stretched = np.clip((data - mins_v) / ranges * 255, 0, 255).astype(np.uint8)
        count, h, w = data.shape
        if count == 1:
            rgb = np.repeat(stretched, 3, axis=0)
        elif count == 2:
            rgb = np.concatenate([stretched, np.zeros((1, h, w), dtype=np.uint8)], axis=0)
        else:
            rgb = stretched[:3]
        alpha = (np.any(data > 0, axis=0)).astype(np.uint8) * 255
        return np.dstack([rgb.transpose(1, 2, 0), alpha])

    def __del__(self):
        if hasattr(self, '_src') and self._src:
            self._src.close()
