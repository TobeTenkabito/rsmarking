import uuid
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, JSONB
from sqlalchemy.orm import declarative_base, relationship
from geoalchemy2 import Geometry
from sqlalchemy import (
    Column, String, DateTime, ForeignKey, func,
    BigInteger, Index, text, Integer, Boolean
)
Base = declarative_base()


class Project(Base):
    __tablename__ = "projects"
    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)

    # server_default letdatabasetimestamps,when
    created_at = Column(DateTime(timezone=True), server_default=func.now(), index=True)

    layers = relationship("Layer", back_populates="project", cascade="all, delete-orphan")


class Layer(Base):
    __tablename__ = "layers"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id = Column(PG_UUID(as_uuid=True), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False,
                        index=True)
    name = Column(String(255), nullable=False)

    # text ID,BigInteger text ID (text Snowflake)
    source_raster_index_id = Column(BigInteger, nullable=True, index=True)

    project = relationship("Project", back_populates="layers")
    features = relationship("Feature", back_populates="layer", cascade="all, delete-orphan")


class LayerField(Base):
    """
    new model,exists independently,does not affect existing models.
    holds unidirectional layer_id foreign key only,no need on Layer add reverse relation.
    """
    __tablename__ = "layer_fields"
    __table_args__ = (
        Index("ix_layer_fields_layer_id", "layer_id"),
    )

    id          = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layer_id    = Column(PG_UUID(as_uuid=True), ForeignKey("layers.id", ondelete="CASCADE"), nullable=False)
    field_name  = Column(String, nullable=False)   # JSONB key
    field_alias = Column(String)                   # frontend display name
    field_type  = Column(String, nullable=False)   # string / number / boolean / date
    field_order = Column(Integer, default=0)
    is_required = Column(Boolean, default=False)
    is_system   = Column(Boolean, default=False)   # True = text,not deletable
    default_val = Column(String)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())


class Feature(Base):
    __tablename__ = "features"

    id = Column(PG_UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    layer_id = Column(PG_UUID(as_uuid=True), ForeignKey("layers.id", ondelete="CASCADE"), nullable=False, index=True)

    # 1. core fix:spatial_index=False fully avoid Alembic during upgrade DuplicateTableError
    geom = Column(
        Geometry(geometry_type='GEOMETRY', srid=4326, spatial_index=False),
        nullable=False
    )

    category = Column(String(100), index=True)

    # 2. JSONB performance optimization:text PostgreSQL text JSONB text Gin than regular JSON much faster
    properties = Column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)
    meta = Column(JSONB, server_default=text("'{}'::jsonb"), nullable=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    layer = relationship("Layer", back_populates="features")

    # 3. explicit index definition
    __table_args__ = (
        Index('idx_features_geom', 'geom', postgresql_using='gist'),
        Index('idx_features_properties_gin', 'properties', postgresql_using='gin'),
        Index('idx_layer_category', 'layer_id', 'category'),
    )
