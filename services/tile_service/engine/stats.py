import numpy as np


class StatsManager:
    def __init__(self):
        self.cache = {}

    def get_stretch_params(self, data, band_indices, src, stats_override=None):
        mins, maxs = [], []
        for i, b_idx in enumerate(band_indices):
            b_str = str(b_idx)
            if stats_override and b_str in stats_override:
                mins.append(stats_override[b_str].get('low', 0))
                maxs.append(stats_override[b_str].get('high', 1000))
            elif b_idx in self.cache:
                mins.append(self.cache[b_idx][0])
                maxs.append(self.cache[b_idx][1])
            else:
                b_meta = src.tags(b_idx)
                m_min = b_meta.get('STATISTICS_MINIMUM')
                m_max = b_meta.get('STATISTICS_MAXIMUM')
                if m_min is not None and m_max is not None:
                    val = (float(m_min), float(m_max))
                    self.cache[b_idx] = val
                    mins.append(val[0])
                    maxs.append(val[1])
                else:
                    valid_mask = data[i] > 0
                    valid_data = data[i][valid_mask]
                    if valid_data.size > 500:
                        sample = valid_data[::10]
                        low, high = np.percentile(sample, [2, 98])
                        mins.append(low)
                        maxs.append(high)
                    elif valid_data.size > 0:
                        mins.append(np.min(valid_data))
                        maxs.append(np.max(valid_data))
                    else:
                        mins.append(0); maxs.append(1)
        return np.array(mins, dtype=np.float32), np.array(maxs, dtype=np.float32)
