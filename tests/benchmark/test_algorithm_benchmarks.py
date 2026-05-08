import os
import time

import numpy as np
import pytest

from functions.implement.extraction import extract_building, extract_cloud, extract_vegetation, extract_water
from functions.implement.spectral_indices import calculate_ndvi_array


pytestmark = pytest.mark.benchmark


def _require_benchmarks_enabled():
    if os.getenv("RS_RUN_BENCHMARKS") != "1":
        pytest.skip("Set RS_RUN_BENCHMARKS=1 to run benchmark tests.")


def _time_call(func, *args, runs=5, **kwargs):
    start = time.perf_counter()
    result = None
    for _ in range(runs):
        result = func(*args, **kwargs)
    elapsed_ms = (time.perf_counter() - start) * 1000 / runs
    return elapsed_ms, result


def _synthetic_reflectance(size=512):
    y, x = np.indices((size, size), dtype=np.float32)
    gradient = (x + y) / (2 * size)
    red = 0.15 + gradient * 0.20
    nir = 0.20 + gradient * 0.45
    green = 0.18 + gradient * 0.25
    swir = 0.10 + gradient * 0.40
    blue = 0.10 + gradient * 0.25
    return blue.astype("float32"), green.astype("float32"), red.astype("float32"), nir.astype("float32"), swir.astype("float32")


def test_spectral_index_512_latency_budget():
    _require_benchmarks_enabled()
    _, _, red, nir, _ = _synthetic_reflectance()

    latency_ms, result = _time_call(calculate_ndvi_array, red, nir, runs=10)

    assert result.shape == red.shape
    assert latency_ms < 100.0
    print(f"NDVI 512x512 latency: {latency_ms:.2f} ms")


def test_extraction_modes_512_latency_budget():
    _require_benchmarks_enabled()
    blue, green, red, nir, swir = _synthetic_reflectance()

    cases = [
        ("vegetation_ndvi", extract_vegetation, [red, nir], {"threshold": 0.25}),
        ("water_mndwi", extract_water, [green, swir], {"threshold": 0.0, "mode": "mndwi"}),
        ("building_ndbi", extract_building, [swir, nir, red, green], {"threshold": 0.0, "mode": "ndbi"}),
        ("cloud_threshold", extract_cloud, [blue, swir], {"threshold": 0.2, "mode": "default"}),
    ]

    for name, func, bands, kwargs in cases:
        latency_ms, mask = _time_call(func, bands, runs=5, **kwargs)
        assert mask.shape == blue.shape
        assert mask.dtype == np.uint8
        assert latency_ms < 250.0
        print(f"{name} 512x512 latency: {latency_ms:.2f} ms")
