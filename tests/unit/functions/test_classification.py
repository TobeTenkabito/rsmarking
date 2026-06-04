import numpy as np
import pytest

rasterio = pytest.importorskip("rasterio")
from rasterio.transform import from_origin

from functions.implement.classification import (
    supervised_classification,
    unsupervised_classification,
)
from functions.implement.segmentation import deep_learning_segmentation


def _write_raster(path, data):
    if data.ndim == 2:
        data = data[np.newaxis, ...]
    with rasterio.open(
        path,
        "w",
        driver="GTiff",
        height=data.shape[1],
        width=data.shape[2],
        count=data.shape[0],
        dtype="float32",
        crs="EPSG:3857",
        transform=from_origin(0, data.shape[1], 1, 1),
    ) as dst:
        dst.write(data.astype("float32"))


def test_supervised_classification_uses_labeled_pixels(tmp_path):
    source = tmp_path / "source.tif"
    output = tmp_path / "supervised.tif"
    data = np.zeros((2, 6, 6), dtype=np.float32)
    data[:, :3, :] = np.array([1, 2], dtype=np.float32)[:, None, None]
    data[:, 3:, :] = np.array([8, 9], dtype=np.float32)[:, None, None]
    _write_raster(source, data)

    result = supervised_classification(
        str(source),
        str(output),
        samples=[
            {"row": 1, "col": 1, "class_id": 1},
            {"row": 4, "col": 1, "class_id": 2},
        ],
        classifier="nearest_centroid",
    )

    with rasterio.open(output) as classified:
        labels = classified.read(1)
        assert classified.dtypes[0] == "uint16"
        assert labels[1, 1] == 1
        assert labels[4, 1] == 2
    assert result["class_count"] == 2
    assert result["training_sample_count"] == 2


def test_unsupervised_classification_creates_requested_classes(tmp_path):
    source = tmp_path / "source.tif"
    output = tmp_path / "unsupervised.tif"
    data = np.zeros((1, 8, 8), dtype=np.float32)
    data[:, :4, :] = 1
    data[:, 4:, :] = 10
    _write_raster(source, data)

    result = unsupervised_classification(
        str(source),
        str(output),
        n_classes=2,
        method="kmeans",
        random_seed=7,
    )

    with rasterio.open(output) as classified:
        labels = classified.read(1)
        assert classified.dtypes[0] == "uint16"
        assert set(np.unique(labels)) == {1, 2}
    assert result["class_count"] == 2


def test_deep_learning_segmentation_builtin_backend(tmp_path):
    source = tmp_path / "source.tif"
    output = tmp_path / "segmentation.tif"
    data = np.zeros((3, 8, 8), dtype=np.float32)
    data[:, :4, :] = np.array([0.1, 0.2, 0.3], dtype=np.float32)[:, None, None]
    data[:, 4:, :] = np.array([0.8, 0.7, 0.6], dtype=np.float32)[:, None, None]
    _write_raster(source, data)

    result = deep_learning_segmentation(
        str(source),
        str(output),
        backend="spectral_spatial",
        n_classes=2,
        random_seed=3,
        smoothing=0,
    )

    with rasterio.open(output) as segmented:
        labels = segmented.read(1)
        assert segmented.dtypes[0] == "uint16"
        assert set(np.unique(labels)) == {1, 2}
    assert result["operation"] == "deep_learning_segmentation"
