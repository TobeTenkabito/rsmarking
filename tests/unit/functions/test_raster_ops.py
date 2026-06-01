import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
pytest.importorskip("shapely")
from rasterio.transform import from_origin
from shapely.geometry import box

from functions.implement.manipulation import extract_raster_bands, merge_raster_bands
from functions.implement.resampling import resample_raster
from functions.implement.rasterize_ops import raster_to_vector, vector_to_raster


def _write_raster(path, data, dtype="float32"):
    if data.ndim == 2:
        data = data[np.newaxis, ...]

    meta = {
        "driver": "GTiff",
        "height": data.shape[1],
        "width": data.shape[2],
        "count": data.shape[0],
        "dtype": dtype,
        "crs": "EPSG:3857",
        "transform": from_origin(0, data.shape[1], 1, 1),
    }

    with rasterio.open(path, "w", **meta) as dst:
        dst.write(data.astype(dtype))

    return meta


def test_extract_raster_bands_preserves_selected_order(tmp_path):
    data = np.stack([
        np.full((4, 4), 1, dtype=np.float32),
        np.full((4, 4), 2, dtype=np.float32),
        np.full((4, 4), 3, dtype=np.float32),
    ])
    src = tmp_path / "source.tif"
    out = tmp_path / "selected.tif"
    _write_raster(src, data)

    assert extract_raster_bands(str(src), str(out), [3, 1]) is True

    with rasterio.open(out) as result:
        assert result.count == 2
        np.testing.assert_array_equal(result.read(1), data[2])
        np.testing.assert_array_equal(result.read(2), data[0])


def test_extract_raster_bands_rejects_out_of_range_band(tmp_path):
    src = tmp_path / "source.tif"
    out = tmp_path / "selected.tif"
    _write_raster(src, np.ones((2, 4, 4), dtype=np.float32))

    with pytest.raises(ValueError):
        extract_raster_bands(str(src), str(out), [1, 3])


def test_merge_raster_bands_writes_all_input_bands(tmp_path):
    first = tmp_path / "first.tif"
    second = tmp_path / "second.tif"
    out = tmp_path / "merged.tif"
    _write_raster(first, np.full((1, 4, 4), 7, dtype=np.float32))
    _write_raster(second, np.stack([
        np.full((4, 4), 8, dtype=np.float32),
        np.full((4, 4), 9, dtype=np.float32),
    ]))

    assert merge_raster_bands([str(first), str(second)], str(out)) is True

    with rasterio.open(out) as result:
        assert result.count == 3
        assert result.read(1)[0, 0] == 7
        assert result.read(2)[0, 0] == 8
        assert result.read(3)[0, 0] == 9


def test_resample_raster_uses_source_resolution_units(tmp_path):
    src = tmp_path / "source.tif"
    out = tmp_path / "resampled.tif"
    _write_raster(src, np.arange(16, dtype=np.float32).reshape(4, 4))

    result = resample_raster(
        str(src),
        str(out),
        target_resolution_x=2,
        target_resolution_y=2,
        resolution_unit="source",
        resampling_method="nearest",
    )

    with rasterio.open(out) as ds:
        assert ds.width == 2
        assert ds.height == 2
        assert ds.res == (2.0, 2.0)
        assert ds.crs.to_string() == "EPSG:3857"
        assert result["resolution"] == (2.0, 2.0)


def test_resample_raster_meter_mode_projects_geographic_sources(tmp_path):
    src = tmp_path / "wgs84.tif"
    out = tmp_path / "meters.tif"
    data = np.arange(100, dtype=np.float32).reshape(10, 10)

    with rasterio.open(
        src,
        "w",
        driver="GTiff",
        height=10,
        width=10,
        count=1,
        dtype="float32",
        crs="EPSG:4326",
        transform=from_origin(116.0, 40.0, 0.0001, 0.0001),
    ) as dst:
        dst.write(data, 1)

    resample_raster(
        str(src),
        str(out),
        target_resolution_x=30,
        resolution_unit="meters",
        resampling_method="bilinear",
    )

    with rasterio.open(out) as ds:
        assert ds.crs.is_projected
        assert ds.res == (30.0, 30.0)
        assert ds.width > 0
        assert ds.height > 0


def test_vector_to_raster_burns_values_from_shapely_geometry(tmp_path):
    out = tmp_path / "mask.tif"
    template_meta = {
        "height": 6,
        "width": 6,
        "crs": "EPSG:3857",
        "transform": from_origin(0, 6, 1, 1),
    }
    features = [{"geometry": box(1, 1, 4, 4), "value": 5}]

    result_path = vector_to_raster(features, template_meta, str(out), all_touched=False)

    assert result_path == str(out)
    with rasterio.open(out) as result:
        arr = result.read(1)
        assert result.crs.to_string() == "EPSG:3857"
        assert arr.max() == 5
        assert arr.sum() > 0


def test_raster_to_vector_polygonizes_nonzero_pixels(tmp_path):
    raster_path = tmp_path / "classes.tif"
    data = np.array(
        [
            [0, 0, 0, 0],
            [0, 2, 2, 0],
            [0, 2, 2, 0],
            [0, 0, 0, 3],
        ],
        dtype=np.uint8,
    )
    _write_raster(raster_path, data, dtype="uint8")

    features = raster_to_vector(str(raster_path), skip_zero=True)

    values = sorted(feature["properties"]["raster_value"] for feature in features)
    assert values == [2, 3]
    assert all(feature["geometry"]["type"] == "Polygon" for feature in features)
