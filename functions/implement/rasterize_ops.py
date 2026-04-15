import rasterio
from rasterio.features import rasterize
from shapely.geometry.base import BaseGeometry
from typing import List, Dict, Any, Generator, Tuple


def vector_to_raster(
        features: List[Dict[str, Any]],
        template_meta: Dict[str, Any],
        out_path: str,
        all_touched: bool = False,
        dtype: str = rasterio.uint8,
        nodata: int = 0
) -> str:
    """
    将矢量要素转换为栅格文件 (TIFF)

    工业级优化：
    1. 支持生成器惰性求值，防止千万级矢量导致 OOM
    2. 兼容 Shapely 对象与 GeoJSON 字典
    3. 支持动态烧录值读取
    """

    # 1. 使用生成器 (Generator) 替代列表推导式
    # 空间复杂度从 O(N) 降低至 O(1)
    def shape_generator() -> Generator[Tuple[BaseGeometry, int], None, None]:
        for f in features:
            geom = f['geometry']

            # 兼容性兜底：如果在外部没有被转化为 shapely 对象，则在此转换
            if not isinstance(geom, BaseGeometry):
                from shapely.geometry import shape
                geom = shape(geom)

            # 读取外部计算好的烧录值 (burn value)，如果不存在则默认 1
            val = f.get('value', 1)
            yield (geom, val)

    # 2. 创建输出掩码阵列 (C底层实现，速度极快)
    out_arr = rasterize(
        shapes=shape_generator(),
        out_shape=(template_meta['height'], template_meta['width']),
        transform=template_meta['transform'],
        fill=nodata,
        all_touched=all_touched,
        dtype=dtype
    )

    # 3. 写入文件
    with rasterio.open(
            out_path,
            'w',
            driver='GTiff',
            height=template_meta['height'],
            width=template_meta['width'],
            count=1,
            dtype=dtype,
            crs=template_meta['crs'],
            transform=template_meta['transform'],
            nodata=nodata,
            compress='lzw',
            predictor=2  # 对整型栅格数据有极大压缩增益的预测器
    ) as dst:
        dst.write(out_arr, 1)

    return out_path