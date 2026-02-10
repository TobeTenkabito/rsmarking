from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, BigInteger
from services.data_service.database import Base
from datetime import datetime


class RasterMetadata(Base):
    """遥感影像元数据表"""
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
    bounds = Column(JSON)
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
