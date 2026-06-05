import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin

from functions.implement.time_series_analysis import time_series_analysis


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


def _write_series(tmp_path, values):
    paths = []
    for index, value in enumerate(values):
        path = tmp_path / f"series_{index}.tif"
        _write_raster(path, np.full((2, 2), value, dtype=np.float32))
        paths.append(str(path))
    return paths


def test_monthly_composite_groups_dates_and_writes_tags(tmp_path):
    paths = _write_series(tmp_path, [1, 3, 10])
    output = tmp_path / "monthly.tif"

    result = time_series_analysis(
        paths,
        str(output),
        operation="monthly_composite",
        dates=["2024-01-01", "2024-01-20", "2024-02-01"],
    )

    with rasterio.open(output) as ds:
        data = ds.read()
        assert ds.count == 2
        assert ds.tags()["TIME_SERIES_ANALYSIS"] == "true"
        assert ds.tags()["TIME_SERIES_OPERATION"] == "monthly_composite"
        np.testing.assert_allclose(data[0], np.full((2, 2), 2, dtype=np.float32))
        np.testing.assert_allclose(data[1], np.full((2, 2), 10, dtype=np.float32))
    assert result["groups"] == ["2024-01", "2024-02"]


@pytest.mark.parametrize(
    ("operation", "expected"),
    [
        ("maximum_composite", 5),
        ("median_composite", 3),
    ],
)
def test_value_composites_reduce_full_series(tmp_path, operation, expected):
    paths = _write_series(tmp_path, [1, 5, 3])
    output = tmp_path / f"{operation}.tif"

    result = time_series_analysis(paths, str(output), operation=operation)

    with rasterio.open(output) as ds:
        assert ds.count == 1
        np.testing.assert_allclose(ds.read(1), np.full((2, 2), expected, dtype=np.float32))
    assert result["time_series_operation"] == operation


def test_moving_window_smoothing_uses_temporal_neighbors(tmp_path):
    paths = _write_series(tmp_path, [1, 3, 5])
    output = tmp_path / "moving.tif"

    time_series_analysis(
        paths,
        str(output),
        operation="moving_window_smoothing",
        moving_window_size=3,
    )

    with rasterio.open(output) as ds:
        data = ds.read()
        assert ds.count == 3
        assert data[:, 0, 0].tolist() == pytest.approx([2, 3, 4])


def test_savitzky_golay_preserves_linear_series(tmp_path):
    paths = _write_series(tmp_path, [1, 2, 3, 4, 5])
    output = tmp_path / "savgol.tif"

    result = time_series_analysis(
        paths,
        str(output),
        operation="savitzky_golay",
        savgol_window_length=3,
        savgol_polyorder=1,
    )

    with rasterio.open(output) as ds:
        np.testing.assert_allclose(ds.read()[:, 0, 0], np.array([1, 2, 3, 4, 5], dtype=np.float32), atol=1e-5)
    assert result["savgol_window_length"] == 3
    assert result["savgol_polyorder"] == 1


def test_trend_outputs_slope_intercept_and_r2(tmp_path):
    paths = _write_series(tmp_path, [1, 3, 5])
    output = tmp_path / "trend.tif"

    time_series_analysis(
        paths,
        str(output),
        operation="trend",
        dates=["2024-01-01", "2024-01-02", "2024-01-03"],
    )

    with rasterio.open(output) as ds:
        trend = ds.read()
        assert ds.count == 3
        assert trend[0, 0, 0] == pytest.approx(2.0)
        assert trend[1, 0, 0] == pytest.approx(1.0)
        assert trend[2, 0, 0] == pytest.approx(1.0)


def test_seasonality_and_phenology_extract_timing_parameters(tmp_path):
    paths = _write_series(tmp_path, [1, 2, 5, 3, 1])
    dates = ["2024-01-01", "2024-01-02", "2024-01-03", "2024-01-04", "2024-01-05"]
    seasonality_output = tmp_path / "seasonality.tif"
    phenology_output = tmp_path / "phenology.tif"

    time_series_analysis(paths, str(seasonality_output), operation="seasonality", dates=dates)
    time_series_analysis(
        paths,
        str(phenology_output),
        operation="phenology",
        dates=dates,
        phenology_threshold_ratio=0.25,
    )

    with rasterio.open(seasonality_output) as ds:
        seasonality = ds.read()
        assert ds.count == 4
        assert seasonality[0, 0, 0] == pytest.approx(2.4)
        assert seasonality[1, 0, 0] == pytest.approx(4.0)
        assert seasonality[2, 0, 0] == pytest.approx(3.0)
        assert seasonality[3, 0, 0] == pytest.approx(1.0)

    with rasterio.open(phenology_output) as ds:
        phenology = ds.read()
        assert ds.count == 5
        assert phenology[0, 0, 0] == pytest.approx(2.0)
        assert phenology[1, 0, 0] == pytest.approx(4.0)
        assert phenology[2, 0, 0] == pytest.approx(3.0)
        assert phenology[3, 0, 0] == pytest.approx(2.0)
        assert phenology[4, 0, 0] == pytest.approx(4.0)
