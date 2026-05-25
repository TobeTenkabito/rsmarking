import pytest

pytest.importorskip("cachetools")
pytest.importorskip("diskcache")

from services.tile_service.core.cache import TileCache


def test_tile_cache_same_parameters_hit(tmp_path):
    cache = TileCache(l1_size=8, l2_dir=str(tmp_path / "cache"), l2_limit=1024 * 1024)
    data = b"png-bytes"

    cache.set_tile(
        "idx",
        1,
        2,
        3,
        "1,2,3",
        data,
        stats={"low": 1, "high": 9},
        file_version=123,
        tile_size=256,
        renderer_version="render_v2",
        alpha_strategy="mask_auto",
    )

    assert cache.get_tile(
        "idx",
        1,
        2,
        3,
        "1,2,3",
        stats={"high": 9, "low": 1},
        file_version=123,
        tile_size=256,
        renderer_version="render_v2",
        alpha_strategy="mask_auto",
    ) == data


def test_tile_cache_different_stats_do_not_hit(tmp_path):
    cache = TileCache(l1_size=8, l2_dir=str(tmp_path / "cache"), l2_limit=1024 * 1024)
    cache.set_tile("idx", 1, 2, 3, "1", b"a", stats={"low": 1, "high": 9})

    assert cache.get_tile("idx", 1, 2, 3, "1", stats={"low": 2, "high": 9}) is None


def test_tile_cache_different_file_version_does_not_hit(tmp_path):
    cache = TileCache(l1_size=8, l2_dir=str(tmp_path / "cache"), l2_limit=1024 * 1024)
    cache.set_tile("idx", 1, 2, 3, "1", b"a", file_version=1)

    assert cache.get_tile("idx", 1, 2, 3, "1", file_version=2) is None


def test_tile_cache_different_tile_size_or_renderer_do_not_hit(tmp_path):
    cache = TileCache(l1_size=8, l2_dir=str(tmp_path / "cache"), l2_limit=1024 * 1024)
    cache.set_tile(
        "idx",
        1,
        2,
        3,
        "1",
        b"a",
        tile_size=256,
        renderer_version="render_v2",
    )

    assert cache.get_tile("idx", 1, 2, 3, "1", tile_size=512, renderer_version="render_v2") is None
    assert cache.get_tile("idx", 1, 2, 3, "1", tile_size=256, renderer_version="render_v3") is None


def test_tile_cache_preserves_legacy_key_shape(tmp_path):
    cache = TileCache(l1_size=8, l2_dir=str(tmp_path / "cache"), l2_limit=1024 * 1024)

    assert cache._make_key("idx", 1, 2, 3, "1,2,3") == "idx/1/2/3/1,2,3"
    assert cache._make_key("idx", 1, 2, 3, "1", {"low": 1, "high": 9}).count("/") == 5
