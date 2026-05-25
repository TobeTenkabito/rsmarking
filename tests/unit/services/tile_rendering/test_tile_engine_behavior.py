import numpy as np
import pytest

pytest.importorskip("rasterio")
from rasterio.transform import from_origin

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
