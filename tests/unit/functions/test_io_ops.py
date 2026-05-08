import pytest

pytest.importorskip("osgeo")
from functions.implement import io_ops


def test_build_raster_overviews_resets_gdal_options(monkeypatch):
    calls = []

    class FakeDataset:
        def BuildOverviews(self, resampling, levels):
            calls.append(("BuildOverviews", resampling, tuple(levels)))

    monkeypatch.setattr(io_ops.gdal, "SetConfigOption", lambda key, value: calls.append((key, value)))
    monkeypatch.setattr(io_ops.gdal, "Open", lambda path, mode: FakeDataset())

    assert io_ops.build_raster_overviews("example.tif", levels=[2], resampling="AVERAGE") is True

    assert ("BuildOverviews", "AVERAGE", (2,)) in calls
    assert ("GDAL_NUM_THREADS", None) in calls
    assert ("COMPRESS_OVERVIEW", None) in calls


def test_convert_raster_to_cog_uses_available_cog_driver(monkeypatch, tmp_path):
    events = []

    class FakeBand:
        def GetOverviewCount(self):
            return 1

    class FakeDataset:
        def GetRasterBand(self, index):
            return FakeBand()

        def FlushCache(self):
            events.append("source_flush")

    class FakeResultDataset:
        def FlushCache(self):
            events.append("result_flush")

    class FakeDriver:
        def CreateCopy(self, output_path, ds, strict=0, options=None):
            events.append(("CreateCopy", output_path, tuple(options or ())))
            return FakeResultDataset()

    monkeypatch.setattr(io_ops.gdal, "Open", lambda path, mode: FakeDataset())
    monkeypatch.setattr(io_ops.gdal, "GetDriverByName", lambda name: FakeDriver() if name == "COG" else None)

    out = tmp_path / "out" / "test.tif"
    assert io_ops.convert_raster_to_cog("input.tif", str(out), block_size=256) is True

    create_copy = next(event for event in events if isinstance(event, tuple))
    assert create_copy[0] == "CreateCopy"
    assert create_copy[1] == str(out)
    assert "BLOCKXSIZE=256" in create_copy[2]
    assert "result_flush" in events
