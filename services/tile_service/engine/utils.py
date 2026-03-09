import mercantile
from rasterio.windows import from_bounds


def get_tile_window(x, y, z, src, transformer):
    tile_wgs84 = mercantile.bounds(x, y, z)
    left, bottom = transformer.transform(tile_wgs84.west, tile_wgs84.south)
    right, top = transformer.transform(tile_wgs84.east, tile_wgs84.north)
<<<<<<< HEAD
    return from_bounds(left, bottom, right, top, transform=src.transform)
=======
    return from_bounds(left, bottom, right, top, transform=src.transform)
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
