from pydantic import BaseModel


class ClipRasterByVectorRequest(BaseModel):
    """矢量裁剪栅格请求体"""
    raster_id: int                        # 被裁剪的栅格 ID
    new_name: str                         # 输出文件名
    geometries: list[dict]                # GeoJSON geometry 对象列表
    src_vector_crs: str = "EPSG:4326"     # 矢量坐标系
    crop: bool = True                     # 是否裁剪到最小外接矩形
    nodata: float | None = None           # 掩膜外填充值
    all_touched: bool = False             # 边界像元是否纳入掩膜


class ClipVectorByRasterRequest(BaseModel):
    """栅格裁剪矢量请求体"""
    raster_id: int                        # 提供空间范围的栅格 ID
    features: list[dict]                  # GeoJSON Feature 对象列表
    src_vector_crs: str = "EPSG:4326"     # 矢量坐标系
    mode: str = "intersects"              # intersects / within / clip
