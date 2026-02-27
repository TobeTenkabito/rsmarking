from sqlalchemy import Column, String, DateTime, ForeignKey, func, BigInteger
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from geoalchemy2 import Geometry
import uuid

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    layers = relationship("Layer", back_populates="project", cascade="all, delete-orphan")


class Layer(Base):
    __tablename__ = "layers"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(PG_UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False)
    name = Column(String(255), nullable=False)

    # 扩展：记录该图层是基于哪个影像文件标注的
    # 关联到 data_service 中的 RasterMetadata.index_id
    source_raster_index_id = Column(BigInteger, nullable=True, index=True)

    project = relationship("Project", back_populates="layers")
    features = relationship("Feature", back_populates="layer", cascade="all, delete-orphan")


class Feature(Base):
    """
    Core Spatial Feature Model
    """
    __tablename__ = "features"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layer_id = Column(PG_UUID(as_uuid=True), ForeignKey("layers.id"), nullable=False, index=True)

    geom = Column(
        Geometry(geometry_type='GEOMETRY', srid=4326, spatial_index=True),
        nullable=False
    )

    category = Column(String(100), index=True)

    properties = Column(JSONB, server_default='{}')

    meta = Column(JSONB, server_default='{}')

    created_at = Column(DateTime, server_default=func.now())

    layer = relationship("Layer", back_populates="features")
