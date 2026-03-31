from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, BigInteger, Boolean, ForeignKey, Index
from services.data_service.database import Base
from datetime import datetime


class RasterMetadata(Base):
    """栅格元数据表"""
    __tablename__ = "raster_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(255), nullable=False)
    # 索引标识，用于索引单个文件
    index_id = Column(BigInteger, index=True, unique=True, nullable=False)

    # 关联标识：用于将多个文件（如不同波段）组合在一起
    bundle_id = Column(String(100), index=True, nullable=True)

    # 存储路径
    file_path = Column(String(512), nullable=False)
    cog_path = Column(String(512))

    # 空间属性
    crs = Column(String(500))
    bounds = Column(JSON)  # 原始坐标
    bounds_wgs84 = Column(JSON, nullable=True)  # wgs84坐标
    center = Column(JSON)

    # 影像参数
    width = Column(Integer)
    height = Column(Integer)
    bands = Column(Integer)
    data_type = Column(String(50))

    # 分辨率
    resolution_x = Column(Float)
    resolution_y = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)


class RasterField(Base):
    """栅格业务属性字段表"""
    __tablename__ = "raster_fields"
    __table_args__ = (
        Index("ix_raster_fields_raster_index_id", "raster_index_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # 关联 RasterMetadata.index_id（雪花ID），级联删除
    raster_index_id = Column(
        BigInteger,
        ForeignKey("raster_metadata.index_id", ondelete="CASCADE"),
        nullable=False
    )
    field_name  = Column(String, nullable=False)   # 字段键名
    field_alias = Column(String, nullable=True)    # 前端显示名
    field_type  = Column(String, nullable=False)   # string / number / boolean / date
    field_order = Column(Integer, default=0)
    is_required = Column(Boolean, default=False)
    is_system   = Column(Boolean, default=False)   # True 时前端不可删除
    default_val = Column(String, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
