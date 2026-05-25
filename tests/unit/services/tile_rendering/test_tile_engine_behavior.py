from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, get_ident

import numpy as np
import pytest

pytest.importorskip("rasterio")
from rasterio.transform import from_origin

from services.tile_service.engine import tiler
from services.tile_service.engine.tiler import TileEngine


class FakeMaskFlag:
    def __init__(self, name):
        self.name = name


class FakeDataset:
    def __init__(self, data):
        self.data = data
        self.count = data.shape[0]
        self.crs = "EPSG:3857"
        self.width = data.shape[2]
        self.height = data.shape[1]
        self.transform = from_origin(0, 0, 1, 1)
        self.closed = False
        self.nodata = None
        self.mask_flag_enums = [[FakeMaskFlag("all_valid")] for _ in range(self.count)]

    def read(self, bands, **kwargs):
        return self.data[np.array(bands) - 1]

    def read_masks(self, bands, **kwargs):
        shape = (len(bands), self.data.shape[1], self.data.shape[2])
        return np.full(shape, 255, dtype=np.uint8)

    def close(self):
        self.closed = True

    def tags(self, band=None):
        return {}

    def overviews(self, band):
        return []


def _patch_engine_io(mocker, data):
    mocker.patch("services.tile_service.engine.tiler.HAS_FAST_TILER", False)
    mocker.patch("services.tile_service.engine.tiler.fast_stretch_and_stack", None)
    mocker.patch("services.tile_service.engine.tiler.get_tile_window", return_value=None)
    mocker.patch("services.tile_service.engine.tiler.os.path.exists", return_value=True)
    mocker.patch(
        "services.tile_service.engine.tiler.rasterio.open",
        return_value=FakeDataset(data),
    )


def test_tile_engine_missing_file_returns_none(tmp_path):
    assert TileEngine(str(tmp_path / "missing.tif")).read_tile(0, 0, 0, bands=[1]) is None


def test_tile_engine_all_zero_tile_returns_none(mocker):
    data = np.zeros((1, 256, 256), dtype=np.float32)
    _patch_engine_io(mocker, data)

    assert TileEngine("fake.tif").read_tile(0, 0, 0, bands=[1]) is None


def test_tile_engine_single_band_outputs_rgba_with_identical_rgb(mocker):
    data = np.full((1, 256, 256), 7.0, dtype=np.float32)
    _patch_engine_io(mocker, data)

    tile = TileEngine("fake.tif").read_tile(0, 0, 0, bands=[1])

    assert tile is not None
    assert tile.shape == (256, 256, 4)
    assert np.array_equal(tile[:, :, 0], tile[:, :, 1])
    assert np.array_equal(tile[:, :, 1], tile[:, :, 2])


def test_tile_engine_three_band_outputs_rgba(mocker):
    data = np.stack(
        [
            np.full((256, 256), 10.0, dtype=np.float32),
            np.full((256, 256), 20.0, dtype=np.float32),
            np.full((256, 256), 30.0, dtype=np.float32),
        ]
    )
    _patch_engine_io(mocker, data)

    tile = TileEngine("fake.tif").read_tile(0, 0, 0, bands=[1, 2, 3])

    assert tile is not None
    assert tile.shape == (256, 256, 4)


def test_tile_engine_thread_local_reuses_current_thread_handle(mocker, monkeypatch):
    data = np.full((1, 256, 256), 7.0, dtype=np.float32)
    opened = []

    def open_dataset(path):
        dataset = FakeDataset(data)
        opened.append(dataset)
        return dataset

    monkeypatch.setattr(tiler.settings, "TILE_RASTER_OPEN_MODE", "thread_local")
    mocker.patch("services.tile_service.engine.tiler.HAS_FAST_TILER", False)
    mocker.patch("services.tile_service.engine.tiler.fast_stretch_and_stack", None)
    mocker.patch("services.tile_service.engine.tiler.get_tile_window", return_value=None)
    mocker.patch("services.tile_service.engine.tiler.os.path.exists", return_value=True)
    mocker.patch("services.tile_service.engine.tiler._file_mtime_ns", return_value=100)
    mocker.patch("services.tile_service.engine.tiler.rasterio.open", side_effect=open_dataset)

    engine = TileEngine("fake.tif")
    assert engine.read_tile(0, 0, 0, bands=[1]) is not None
    assert engine.read_tile(0, 0, 0, bands=[1]) is not None

    assert len(opened) == 1
    assert opened[0].closed is False
    engine.close()


def test_tile_engine_thread_local_mtime_change_refreshes_handle(mocker, monkeypatch):
    data = np.full((1, 256, 256), 7.0, dtype=np.float32)
    opened = []

    def open_dataset(path):
        dataset = FakeDataset(data)
        opened.append(dataset)
        return dataset

    monkeypatch.setattr(tiler.settings, "TILE_RASTER_OPEN_MODE", "thread_local")
    mocker.patch("services.tile_service.engine.tiler.HAS_FAST_TILER", False)
    mocker.patch("services.tile_service.engine.tiler.fast_stretch_and_stack", None)
    mocker.patch("services.tile_service.engine.tiler.get_tile_window", return_value=None)
    mocker.patch("services.tile_service.engine.tiler.os.path.exists", return_value=True)
    mocker.patch("services.tile_service.engine.tiler._file_mtime_ns", side_effect=[100, 200])
    invalidate = mocker.patch("services.tile_service.engine.tiler.StatsManager.invalidate_file")
    mocker.patch("services.tile_service.engine.tiler.rasterio.open", side_effect=open_dataset)

    engine = TileEngine("fake.tif")
    assert engine.read_tile(0, 0, 0, bands=[1]) is not None
    assert engine.read_tile(0, 0, 0, bands=[1]) is not None

    assert len(opened) == 2
    assert opened[0].closed is True
    assert opened[1].closed is False
    invalidate.assert_called_with(engine.file_path)
    engine.close()


def test_tile_engine_thread_local_does_not_share_handles_across_threads(mocker, monkeypatch):
    data = np.full((1, 256, 256), 7.0, dtype=np.float32)
    barrier = Barrier(2)
    opened_thread_ids = []

    class BarrierDataset(FakeDataset):
        def read(self, bands, **kwargs):
            barrier.wait(timeout=5)
            return super().read(bands, **kwargs)

    def open_dataset(path):
        opened_thread_ids.append(get_ident())
        return BarrierDataset(data)

    monkeypatch.setattr(tiler.settings, "TILE_RASTER_OPEN_MODE", "thread_local")
    mocker.patch("services.tile_service.engine.tiler.HAS_FAST_TILER", False)
    mocker.patch("services.tile_service.engine.tiler.fast_stretch_and_stack", None)
    mocker.patch("services.tile_service.engine.tiler.get_tile_window", return_value=None)
    mocker.patch("services.tile_service.engine.tiler.os.path.exists", return_value=True)
    mocker.patch("services.tile_service.engine.tiler._file_mtime_ns", return_value=100)
    mocker.patch("services.tile_service.engine.tiler.rasterio.open", side_effect=open_dataset)

    engine = TileEngine("fake.tif")

    def read_tile():
        try:
            return engine.read_tile(0, 0, 0, bands=[1])
        finally:
            engine.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: read_tile(), range(2)))

    assert all(result is not None for result in results)
    assert len(opened_thread_ids) == 2
    assert len(set(opened_thread_ids)) == 2
