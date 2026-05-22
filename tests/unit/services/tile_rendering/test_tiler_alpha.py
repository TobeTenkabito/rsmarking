import numpy as np
import pytest

pytest.importorskip("rasterio")
from rasterio.enums import Resampling
from rasterio.transform import from_origin
from rasterio.windows import Window

from services.tile_service.engine.tiler import TileEngine


class FakeMaskFlag:
    def __init__(self, name):
        self.name = name


class FakeDataset:
    def __init__(self, data, mask_value=255):
        self.data = data
        self.mask_value = mask_value
        self.count = data.shape[0]
        self.crs = "EPSG:3857"
        self.width = data.shape[2]
        self.height = data.shape[1]
        self.transform = from_origin(0, 0, 1, 1)
        self.closed = False
        self.nodata = None
        flag_name = "all_valid" if mask_value == 255 else "per_dataset"
        self.mask_flag_enums = [[FakeMaskFlag(flag_name)] for _ in range(self.count)]

    def read(self, bands, **kwargs):
        return self.data[np.array(bands) - 1]

    def read_masks(self, bands, **kwargs):
        shape = (len(bands), self.data.shape[1], self.data.shape[2])
        return np.full(shape, self.mask_value, dtype=np.uint8)

    def close(self):
        self.closed = True

    def tags(self, band=None):
        return {}

    def overviews(self, band):
        return []


def test_valid_negative_pixels_remain_opaque(mocker):
    data = np.full((1, 256, 256), -0.5, dtype=np.float32)

    mocker.patch("services.tile_service.engine.tiler.HAS_FAST_TILER", False)
    mocker.patch("services.tile_service.engine.tiler.fast_stretch_and_stack", None)
    mocker.patch("services.tile_service.engine.tiler.get_tile_window", return_value=None)
    mocker.patch("services.tile_service.engine.tiler.os.path.exists", return_value=True)
    mocker.patch(
        "services.tile_service.engine.tiler.rasterio.open",
        return_value=FakeDataset(data),
    )

    tile = TileEngine("fake.tif").read_tile(0, 0, 0, bands=[1])

    assert tile is not None
    assert tile.shape == (256, 256, 4)
    assert tile[:, :, 3].min() == 255
    assert tile[:, :, 0].max() > 0


def test_masked_out_tile_returns_empty(mocker):
    data = np.full((1, 256, 256), -0.5, dtype=np.float32)

    mocker.patch("services.tile_service.engine.tiler.HAS_FAST_TILER", False)
    mocker.patch("services.tile_service.engine.tiler.fast_stretch_and_stack", None)
    mocker.patch("services.tile_service.engine.tiler.get_tile_window", return_value=None)
    mocker.patch("services.tile_service.engine.tiler.os.path.exists", return_value=True)
    mocker.patch(
        "services.tile_service.engine.tiler.rasterio.open",
        return_value=FakeDataset(data, mask_value=0),
    )

    tile = TileEngine("fake.tif").read_tile(0, 0, 0, bands=[1])

    assert tile is None


def test_unmasked_zero_fill_connected_to_edge_is_transparent(mocker):
    data = np.ones((3, 256, 256), dtype=np.float32)
    data[:, :, :64] = 0

    mocker.patch("services.tile_service.engine.tiler.HAS_FAST_TILER", False)
    mocker.patch("services.tile_service.engine.tiler.fast_stretch_and_stack", None)
    mocker.patch("services.tile_service.engine.tiler.get_tile_window", return_value=None)
    mocker.patch("services.tile_service.engine.tiler.os.path.exists", return_value=True)
    mocker.patch(
        "services.tile_service.engine.tiler.rasterio.open",
        return_value=FakeDataset(data),
    )

    tile = TileEngine("fake.tif").read_tile(0, 0, 0, bands=[1, 2, 3])

    assert tile is not None
    assert np.all(tile[:, :64, 3] == 0)
    assert np.all(tile[:, 64:, 3] == 255)


def test_unmasked_internal_zero_pixels_stay_opaque(mocker):
    data = np.ones((3, 256, 256), dtype=np.float32)
    data[:, 96:160, 96:160] = 0

    mocker.patch("services.tile_service.engine.tiler.HAS_FAST_TILER", False)
    mocker.patch("services.tile_service.engine.tiler.fast_stretch_and_stack", None)
    mocker.patch("services.tile_service.engine.tiler.get_tile_window", return_value=None)
    mocker.patch("services.tile_service.engine.tiler.os.path.exists", return_value=True)
    mocker.patch(
        "services.tile_service.engine.tiler.rasterio.open",
        return_value=FakeDataset(data),
    )

    tile = TileEngine("fake.tif").read_tile(0, 0, 0, bands=[1, 2, 3])

    assert tile is not None
    assert np.all(tile[:, :, 3] == 255)


def test_large_decimation_without_overviews_uses_nearest():
    data = np.ones((1, 256, 256), dtype=np.float32)
    src = FakeDataset(data)
    engine = TileEngine("fake.tif")
    window = Window(0, 0, 2048, 2048)

    resampling = engine._select_resampling(src, 1, window)

    assert resampling == Resampling.nearest


def test_small_decimation_uses_bilinear():
    data = np.ones((1, 256, 256), dtype=np.float32)
    src = FakeDataset(data)
    engine = TileEngine("fake.tif")
    window = Window(0, 0, 256, 256)

    resampling = engine._select_resampling(src, 1, window)

    assert resampling == Resampling.bilinear
