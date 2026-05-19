import numpy as np
from rasterio.enums import Resampling


# Shared across TileEngine instances. Key: (file_path, band_idx) -> (low, high)
_GLOBAL_FILE_STATS: dict = {}


class StatsManager:
    def __init__(self):
        self.cache = {}

    def clear(self):
        self.cache.clear()

    def get_stretch_params(self, data, band_indices, src, stats_override=None):
        mins, maxs = [], []
        for i, b_idx in enumerate(band_indices):
            low, high = self._get_band_stretch(i, b_idx, data, src, stats_override)
            mins.append(low)
            maxs.append(high)
        return np.array(mins, dtype=np.float32), np.array(maxs, dtype=np.float32)

    def _get_band_stretch(self, band_pos, b_idx, data, src, stats_override):
        override = self._get_stats_override(band_pos, b_idx, stats_override)
        if override is not None:
            return override

        if b_idx in self.cache:
            return self.cache[b_idx]

        b_meta = src.tags(b_idx)
        m_min = b_meta.get("STATISTICS_MINIMUM")
        m_max = b_meta.get("STATISTICS_MAXIMUM")
        if m_min is not None and m_max is not None:
            val = (float(m_min), float(m_max))
            self.cache[b_idx] = val
            return val

        file_path = getattr(src, "name", None)
        if not file_path:
            val = self._compute_tile_stats(data[band_pos], src)
            self.cache[b_idx] = val
            return val

        global_key = (file_path, b_idx)
        if global_key in _GLOBAL_FILE_STATS:
            return _GLOBAL_FILE_STATS[global_key]

        val = self._compute_global_stats(src, b_idx)
        _GLOBAL_FILE_STATS[global_key] = val
        return val

    def _get_stats_override(self, band_pos, b_idx, stats_override):
        if not stats_override:
            return None

        direct = stats_override.get(str(b_idx), stats_override.get(b_idx))
        if direct is not None:
            if isinstance(direct, dict):
                return (
                    float(direct.get("low", 0)),
                    float(direct.get("high", 1000)),
                )
            if isinstance(direct, (list, tuple)) and len(direct) >= 2:
                return (float(direct[0]), float(direct[1]))

        if "low" in stats_override and "high" in stats_override:
            low = self._pick_override_value(stats_override["low"], band_pos, b_idx)
            high = self._pick_override_value(stats_override["high"], band_pos, b_idx)
            if low is not None and high is not None:
                return (float(low), float(high))

        return None

    @staticmethod
    def _pick_override_value(value, band_pos, b_idx):
        if isinstance(value, dict):
            return value.get(str(b_idx), value.get(b_idx))
        if isinstance(value, (list, tuple, np.ndarray)):
            return value[band_pos] if band_pos < len(value) else None
        return value

    def _compute_global_stats(self, src, b_idx: int):
        """
        Uses the coarsest overview when available; otherwise samples the full
        image into at most 512x512 pixels and returns a p2/p98 stretch.
        """
        try:
            overviews = src.overviews(b_idx)
            if overviews:
                factor = overviews[-1]
                out_h = max(64, src.height // factor)
                out_w = max(64, src.width // factor)
            else:
                out_h = min(512, src.height)
                out_w = min(512, src.width)

            thumb = src.read(
                b_idx,
                out_shape=(out_h, out_w),
                resampling=Resampling.nearest,
                out_dtype="float32",
            )

            return self._compute_tile_stats(thumb, src)

        except Exception as e:
            print(f"### [STATS_WARN] band={b_idx} global stats failed: {e}, fallback to (0,1)")
            return (0.0, 1.0)

    def _compute_tile_stats(self, band, src=None):
        band = np.asarray(band, dtype=np.float32)
        mask = band != 0

        nodata = getattr(src, "nodata", None)
        if nodata is not None:
            mask &= band != nodata

        valid = band[mask]
        if valid.size < 10:
            return (0.0, 1.0)

        low, high = np.percentile(valid, [2, 98])
        if high <= low:
            high = low + 1.0

        return (float(low), float(high))

    @staticmethod
    def invalidate_file(file_path: str):
        keys_to_del = [k for k in _GLOBAL_FILE_STATS if k[0] == file_path]
        for k in keys_to_del:
            del _GLOBAL_FILE_STATS[k]
