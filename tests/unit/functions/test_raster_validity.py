import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
pytest.importorskip("shapely")
from rasterio.transform import from_origin
from shapely.geometry import shape

from functions.implement.clip_ops import (
    clip_raster_by_vector,
    clip_vector_by_raster,
)
from functions.implement.raster_validity import valid_pixel_footprint
from services.data_service.processor import RasterProcessor


def _write_raster(
    path,
    data,
    *,
    nodata=None,
    valid_mask=None,
    crs="EPSG:3857",
):
    if data.ndim == 2:
        data = data[np.newaxis, ...]
    with rasterio.Env(GDAL_TIFF_INTERNAL_MASK=True):
        with rasterio.open(
            path,
            "w",
            driver="GTiff",
            height=data.shape[1],
            width=data.shape[2],
            count=data.shape[0],
            dtype=data.dtype,
            crs=crs,
            transform=from_origin(0, data.shape[1], 1, 1),
            nodata=nodata,
        ) as dst:
            dst.write(data)
            if valid_mask is not None:
                dst.write_mask(valid_mask.astype(np.uint8) * 255)


def test_footprint_polygonizes_valid_pixels_instead_of_outer_bounds(tmp_path):
    raster_path = tmp_path / "l_shape.tif"
    data = np.zeros((5, 5), dtype=np.uint8)
    data[1:4, 1] = 7
    data[3, 1:4] = 7
    _write_raster(raster_path, data)

    result = valid_pixel_footprint(str(raster_path), dst_crs="EPSG:3857")
    footprint = shape(result["geometry"])

    assert result["valid_pixel_count"] == 5
    assert footprint.area == pytest.approx(5.0)
    assert footprint.area < shape({
        "type": "Polygon",
        "coordinates": [[
            [1, 1], [4, 1], [4, 4], [1, 4], [1, 1],
        ]],
    }).area
    assert not footprint.contains(shape({
        "type": "Point",
        "coordinates": [2.5, 3.5],
    }))


def test_footprint_honors_explicit_mask_and_preserves_valid_zero(tmp_path):
    raster_path = tmp_path / "masked_zero.tif"
    data = np.zeros((4, 4), dtype=np.uint8)
    valid_mask = np.zeros((4, 4), dtype=bool)
    valid_mask[1, 2] = True
    _write_raster(raster_path, data, valid_mask=valid_mask)

    result = valid_pixel_footprint(str(raster_path), dst_crs="EPSG:3857")

    assert result["valid_pixel_count"] == 1
    assert shape(result["geometry"]).area == pytest.approx(1.0)


def test_vector_clipping_uses_footprint_holes_not_its_bounding_box():
    footprint = {
        "type": "Polygon",
        "coordinates": [[
            [0, 0], [1, 0], [1, 2], [3, 2],
            [3, 3], [0, 3], [0, 0],
        ]],
    }
    feature_in_bbox_but_outside_footprint = {
        "type": "Feature",
        "properties": {"name": "must-not-survive"},
        "geometry": {
            "type": "Polygon",
            "coordinates": [[
                [2, 0.5], [2.5, 0.5], [2.5, 1], [2, 1], [2, 0.5],
            ]],
        },
    }

    result = clip_vector_by_raster(
        footprint,
        [feature_in_bbox_but_outside_footprint],
        mode="clip",
    )

    assert result["features"] == []


def test_clip_writes_pixel_mask_for_non_rectangular_geometry(tmp_path):
    source_path = tmp_path / "source.tif"
    output_path = tmp_path / "clipped.tif"
    cog_path = tmp_path / "clipped_cog.tif"
    data = np.full((5, 5), 3, dtype=np.uint8)
    _write_raster(source_path, data)
    triangle = {
        "type": "Polygon",
        "coordinates": [[
            [0, 0], [5, 0], [0, 5], [0, 0],
        ]],
    }

    result = clip_raster_by_vector(
        str(source_path),
        str(output_path),
        [triangle],
        src_vector_crs="EPSG:3857",
        crop=False,
    )

    with rasterio.open(output_path) as clipped:
        mask = clipped.dataset_mask()
        assert clipped.nodata is None
        assert clipped.mask_flag_enums[0][0].name == "per_dataset"
        assert 0 < np.count_nonzero(mask) < mask.size
        assert result["valid_pixel_count"] == np.count_nonzero(mask)
        valid_pixel_count = np.count_nonzero(mask)

    RasterProcessor.convert_to_cog(str(output_path), str(cog_path))
    with rasterio.open(cog_path) as cog:
        assert cog.mask_flag_enums[0][0].name == "per_dataset"
        assert np.count_nonzero(cog.dataset_mask()) == valid_pixel_count


def test_spectrum_rejects_zero_background_without_explicit_mask(tmp_path):
    raster_path = tmp_path / "sparse.tif"
    data = np.zeros((3, 3), dtype=np.uint8)
    data[1, 1] = 4
    _write_raster(raster_path, data, crs="EPSG:4326")

    with pytest.raises(ValueError, match="valid raster pixel"):
        RasterProcessor.query_spectrum(str(raster_path), 0.5, 2.5)

    result = RasterProcessor.query_spectrum(str(raster_path), 1.5, 1.5)
    assert result["bands"][0]["value"] == 4.0
