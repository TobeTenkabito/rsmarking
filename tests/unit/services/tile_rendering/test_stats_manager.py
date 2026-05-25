from concurrent.futures import ThreadPoolExecutor
from threading import Lock
import time

import numpy as np
import pytest

pytest.importorskip("rasterio")

from services.tile_service.engine.stats import (
    _GLOBAL_FILE_STATS,
    _GLOBAL_FILE_STATS_LOCK,
    StatsManager,
)


class FakeStatsDataset:
    def __init__(self, name):
        self.name = name
        self.height = 64
        self.width = 64
        self.nodata = None

    def tags(self, band=None):
        return {}

    def overviews(self, band):
        return []

    def read(self, band, **kwargs):
        return np.linspace(1, 1000, self.height * self.width, dtype=np.float32).reshape(
            self.height,
            self.width,
        )


def test_stats_manager_concurrent_same_file_band(tmp_path, monkeypatch):
    src = FakeStatsDataset(str(tmp_path / "image.tif"))
    StatsManager.invalidate_file(src.name)
    manager = StatsManager()
    data = np.ones((1, 64, 64), dtype=np.float32)
    compute_calls = 0
    compute_lock = Lock()

    def fake_compute_global_stats(self, compute_src, b_idx):
        nonlocal compute_calls
        time.sleep(0.01)
        with compute_lock:
            compute_calls += 1
        return (2.0, 98.0)

    monkeypatch.setattr(StatsManager, "_compute_global_stats", fake_compute_global_stats)

    def read_stats():
        mins, maxs = manager.get_stretch_params(data, [1], src)
        return float(mins[0]), float(maxs[0])

    with ThreadPoolExecutor(max_workers=8) as executor:
        results = list(executor.map(lambda _: read_stats(), range(24)))

    assert len(set(results)) == 1
    assert results[0][1] > results[0][0]
    assert compute_calls == 1


def test_stats_manager_invalidate_file_removes_matching_keys(tmp_path):
    target = str(tmp_path / "target.tif")
    other = str(tmp_path / "other.tif")

    with _GLOBAL_FILE_STATS_LOCK:
        _GLOBAL_FILE_STATS[(target, 1)] = (1.0, 2.0)
        _GLOBAL_FILE_STATS[(target, 2)] = (3.0, 4.0)
        _GLOBAL_FILE_STATS[(other, 1)] = (5.0, 6.0)

    StatsManager.invalidate_file(target)

    with _GLOBAL_FILE_STATS_LOCK:
        assert (target, 1) not in _GLOBAL_FILE_STATS
        assert (target, 2) not in _GLOBAL_FILE_STATS
        assert _GLOBAL_FILE_STATS[(other, 1)] == (5.0, 6.0)
