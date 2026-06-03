from sqlalchemy import Column, Integer, String, Float, JSON, DateTime, BigInteger, Boolean, ForeignKey, Index
from services.data_service.database import Base
from datetime import datetime


class RasterMetadata(Base):
    """raster metadata table"""
    __tablename__ = "raster_metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    file_name = Column(String(255), nullable=False)
    # index identifier,used to index a single file
    index_id = Column(BigInteger, index=True, unique=True, nullable=False)

    # association identifier:used to combine multiple files(different bands)together
    bundle_id = Column(String(100), index=True, nullable=True)

    # storage path
    file_path = Column(String(512), nullable=False)
    cog_path = Column(String(512))

    # spatial properties
    crs = Column(String(500))
    bounds = Column(JSON)  # source coordinates
    bounds_wgs84 = Column(JSON, nullable=True)  # wgs84coordinates
    center = Column(JSON)

    # imagery parameters
    width = Column(Integer)
    height = Column(Integer)
    bands = Column(Integer)
    data_type = Column(String(50))

    # resolution
    resolution_x = Column(Float)
    resolution_y = Column(Float)

    created_at = Column(DateTime, default=datetime.utcnow)


class RasterField(Base):
    """business attribute field table"""
    __tablename__ = "raster_fields"
    __table_args__ = (
        Index("ix_raster_fields_raster_index_id", "raster_index_id"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    # text RasterMetadata.index_id(textID),cascade delete
    raster_index_id = Column(
        BigInteger,
        ForeignKey("raster_metadata.index_id", ondelete="CASCADE"),
        nullable=False
    )
    field_name  = Column(String, nullable=False)   # field key
    field_alias = Column(String, nullable=True)    # frontend display name
    field_type  = Column(String, nullable=False)   # string / number / boolean / date
    field_order = Column(Integer, default=0)
    is_required = Column(Boolean, default=False)
    is_system   = Column(Boolean, default=False)   # True whencannot be deleted by frontend
    default_val = Column(String, nullable=True)
    created_at  = Column(DateTime, default=datetime.utcnow)
