import uuid
from sqlalchemy import Column, String, DateTime, ForeignKey, func, BigInteger, Index, text
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from geoalchemy2 import Geometry

Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)

    # server_default 让数据库处理时间戳，确保多实例时间一致性
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    layers = relationship("Layer", back_populates="project", cascade="all, delete-orphan")


class Layer(Base):
    __tablename__ = "layers"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
                        index=True)
    name = Column(String(255), nullable=False)

    # 外部关联 ID，BigInteger 匹配分布式 ID (如 Snowflake)
    source_raster_index_id = Column(BigInteger, nullable=True, index=True)

    project = relationship("Project", back_populates="layers")
    features = relationship("Feature", back_populates="layer", cascade="all, delete-orphan")


class Feature(Base):
    __tablename__ = "features"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layer_id = Column(PG_UUID(as_uuid=True), ForeignKey("layers.id", ondelete="CASCADE"), nullable=False, index=True)

    # 1. 核心修复：spatial_index=False 彻底杜绝 Alembic 升级时的 DuplicateTableError
    geom = Column(
        Geometry(geometry_type='GEOMETRY', srid=4326, spatial_index=False),
        nullable=False
    )

    category = Column(String(100), index=True)

    # 2. JSONB 性能优化：在 PostgreSQL 中 JSONB 配合 Gin 索引比普通 JSON 快得多
    properties = Column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    meta = Column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    layer = relationship("Layer", back_populates="features")

    # 3. 工业级显式索引定义
    __table_args__ = (
        Index('idx_features_geom', 'geom', postgresql_using='gist'),
        Index('idx_features_properties_gin', 'properties', postgresql_using='gin'),
        Index('idx_layer_category', 'layer_id', 'category'),
    )
