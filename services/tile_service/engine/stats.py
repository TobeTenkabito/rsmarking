import numpy as np
import rasterio
from rasterio.enums import Resampling


# 文件级全局统计缓存，跨 TileEngine 实例共享
# key: (file_path, band_idx) → (low, high)
_GLOBAL_FILE_STATS: dict = {}


class StatsManager:
    def __init__(self):
        self.cache = {}

    def get_stretch_params(self, data, band_indices, src, stats_override=None):
        mins, maxs = [], []
        for i, b_idx in enumerate(band_indices):
            low, high = self._get_band_stretch(i, b_idx, data, src, stats_override)
            mins.append(low)
            maxs.append(high)
        return np.array(mins, dtype=np.float32), np.array(maxs, dtype=np.float32)

    def _get_band_stretch(self, band_pos, b_idx, data, src, stats_override):
        b_str = str(b_idx)
        file_path = src.name

        if stats_override and b_str in stats_override:
            return (
                float(stats_override[b_str].get('low', 0)),
                float(stats_override[b_str].get('high', 1000)),
            )

        if b_idx in self.cache:
            return self.cache[b_idx]

        b_meta = src.tags(b_idx)
        m_min = b_meta.get('STATISTICS_MINIMUM')
        m_max = b_meta.get('STATISTICS_MAXIMUM')
        if m_min is not None and m_max is not None:
            val = (float(m_min), float(m_max))
            self.cache[b_idx] = val
            return val

        global_key = (file_path, b_idx)
        if global_key in _GLOBAL_FILE_STATS:
            return _GLOBAL_FILE_STATS[global_key]

        val = self._compute_global_stats(src, b_idx)
        _GLOBAL_FILE_STATS[global_key] = val
        return val

    def _compute_global_stats(self, src, b_idx: int):
        """
        利用 rasterio 的 overview（金字塔）做快速全局采样。
        若无 overview，则以 512x512 降采样读取整幅影像。
        返回 (p2, p98) 作为拉伸区间。
        """
        try:
            overviews = src.overviews(b_idx)
            if overviews:
                overview_level = len(overviews)
                factor = overviews[-1]  # e.g. 128
                out_h = max(64, src.height // factor)
                out_w = max(64, src.width // factor)
            else:
                out_h = min(512, src.height)
                out_w = min(512, src.width)

            thumb = src.read(
                b_idx,
                out_shape=(out_h, out_w),
                resampling=Resampling.nearest,
            ).astype(np.float32)

            nodata = src.nodata
            mask = thumb != 0
            if nodata is not None:
                mask &= (thumb != nodata)

            valid = thumb[mask]
            if valid.size < 10:
                return (0.0, 1.0)

            low, high = np.percentile(valid, [2, 98])
            if high <= low:
                high = low + 1.0

            return (float(low), float(high))

        except Exception as e:
            print(f"### [STATS_WARN] band={b_idx} global stats failed: {e}, fallback to (0,1)")
            return (0.0, 1.0)

    @staticmethod
    def invalidate_file(file_path: str):
        """当文件内容更新时，清除该文件的全局统计缓存"""
        keys_to_del = [k for k in _GLOBAL_FILE_STATS if k[0] == file_path]
        for k in keys_to_del:
            del _GLOBAL_FILE_STATS[k]