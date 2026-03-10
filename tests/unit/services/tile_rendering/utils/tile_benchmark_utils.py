import time
import numpy as np
from unittest.mock import patch
from rasterio.transform import from_origin

from services.tile_service.engine.tiler import TileEngine


class FakeDataset:

    def __init__(self, data):

        self.data = data
        self.count = data.shape[0]

        self.crs = "EPSG:3857"
        self.width = data.shape[2]
        self.height = data.shape[1]

        from rasterio.transform import from_origin
        self.transform = from_origin(0,0,1,1)

        self.closed = False

    def read(self, bands, **kwargs):

        bands = np.array(bands) - 1

        return self.data[bands]

    def close(self):

        self.closed = True

    def tags(self, band=None):

        return {}


def benchmark_render(data, runs=50):

    with patch("services.tile_service.engine.tiler.HAS_FAST_TILER", False), \
         patch("services.tile_service.engine.tiler.fast_stretch_and_stack", None), \
         patch("services.tile_service.engine.tiler.get_tile_window", return_value=None), \
         patch("services.tile_service.engine.tiler.os.path.exists", return_value=True), \
         patch("services.tile_service.engine.tiler.rasterio.open", return_value=FakeDataset(data)):

        engine = TileEngine("fake.tif")

        start = time.perf_counter()

        for _ in range(runs):
            engine.read_tile(0,0,0)

        end = time.perf_counter()

        return (end-start)/runs