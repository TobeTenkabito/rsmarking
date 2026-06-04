import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin

from functions.implement.dem_analysis import dem_analysis


def _write_raster(path, data, dtype="float32"):
    if data.ndim == 2:
        data = data[np.newaxis, ...]

    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[1],
        width=data.shape[2],
        count=data.shape[0],
        dtype=dtype,
        crs="EPSG:3857",
        transform=from_origin(0, data.shape[1], 1, 1),
    ) as dst:
        dst.write(data.astype(dtype))


@pytest.mark.parametrize(
    "operation",
    [
        "elevation",
        "slope",
        "aspect",
        "hillshade",
        "curvature",
        "relief",
        "twi",
        "flow_direction",
        "flow_accumulation",
        "watershed",
    ],
)
def test_dem_analysis_writes_each_product(tmp_path, operation):
    source = tmp_path / "dem.tif"
    output = tmp_path / f"{operation}.tif"
    data = np.array(
        [
            [5, 4, 5],
            [4, 0, 4],
            [5, 4, 5],
        ],
        dtype=np.float32,
    )
    _write_raster(source, data)

    result = dem_analysis(str(source), str(output), operation=operation)

    with rasterio.open(output) as ds:
        assert ds.count == 1
        assert ds.width == 3
        assert ds.height == 3
        assert ds.tags()["DEM_ANALYSIS"] == "true"
        assert ds.tags()["DEM_OPERATION"] == operation
    assert result["operation"] == "dem_analysis"
    assert result["dem_operation"] == operation


def test_slope_and_aspect_match_east_rising_plane(tmp_path):
    source = tmp_path / "plane.tif"
    slope_output = tmp_path / "slope.tif"
    aspect_output = tmp_path / "aspect.tif"
    data = np.tile(np.arange(5, dtype=np.float32), (5, 1))
    _write_raster(source, data)

    dem_analysis(str(source), str(slope_output), operation="slope")
    dem_analysis(str(source), str(aspect_output), operation="aspect")

    with rasterio.open(slope_output) as slope_ds:
        slope = slope_ds.read(1)
        assert slope[2, 2] == pytest.approx(45.0, abs=0.1)

    with rasterio.open(aspect_output) as aspect_ds:
        aspect = aspect_ds.read(1)
        assert aspect[2, 2] == pytest.approx(270.0, abs=0.1)


def test_d8_flow_accumulation_and_watershed_drain_to_sink(tmp_path):
    source = tmp_path / "sink.tif"
    flow_output = tmp_path / "flow.tif"
    accumulation_output = tmp_path / "accumulation.tif"
    watershed_output = tmp_path / "watershed.tif"
    data = np.array(
        [
            [5, 4, 5],
            [4, 0, 4],
            [5, 4, 5],
        ],
        dtype=np.float32,
    )
    _write_raster(source, data)

    dem_analysis(str(source), str(flow_output), operation="flow_direction")
    dem_analysis(str(source), str(accumulation_output), operation="flow_accumulation")
    dem_analysis(str(source), str(watershed_output), operation="watershed")

    with rasterio.open(flow_output) as flow_ds:
        flow = flow_ds.read(1)
        assert flow[0, 1] == 4
        assert flow[1, 0] == 1
        assert flow[1, 1] == 0
        assert flow[1, 2] == 16
        assert flow[2, 1] == 64

    with rasterio.open(accumulation_output) as acc_ds:
        accumulation = acc_ds.read(1)
        assert accumulation[1, 1] == pytest.approx(9.0)

    with rasterio.open(watershed_output) as ws_ds:
        labels = ws_ds.read(1)
        assert set(np.unique(labels)) == {1}
