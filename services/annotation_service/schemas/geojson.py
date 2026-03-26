from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Optional
from uuid import UUID
from datetime import datetime


class ProjectBase(BaseModel):
    name: str = Field(..., example="Xiongan New Area Mapping")


class ProjectCreate(ProjectBase):
    pass


class ProjectResponse(ProjectBase):
    id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


class LayerBase(BaseModel):
    name: str = Field(..., example="Buildings_Extraction_V1")
    source_raster_index_id: Optional[int] = Field(None, description="Linked ID from data_service's RasterMetadata")


class LayerCreate(LayerBase):
    pass


class LayerResponse(LayerBase):
    id: UUID
    project_id: UUID

    class Config:
        from_attributes = True


class GeometryModel(BaseModel):
    """
    Standard GeoJSON Geometry model
    """
    type: str = Field(..., json_schema_extra={"example": "Polygon"})
    coordinates: List[Any]


class FeatureCreate(BaseModel):
    """
    Schema for creating a new feature via GeoJSON format
    """
    geometry: GeometryModel
    properties: Optional[Dict[str, Any]] = Field(default_factory=dict)
    category: Optional[str] = None
    srid: int = 4326  # Default input SRID

    @field_validator('geometry')
    @classmethod
    def validate_type(cls, v):
        allowed = ["Point", "LineString", "Polygon", "MultiPolygon", "MultiLineString"]
        if v.type not in allowed:
            raise ValueError(f"Geometry type {v.type} not supported")
        return v


class FeatureUpdate(BaseModel):
    """
    Schema for updating existing features (partial updates)
    """
    geometry: Optional[GeometryModel] = None
    properties: Optional[Dict[str, Any]] = None
    category: Optional[str] = None


class FeatureResponse(BaseModel):
    """
    Standard GeoJSON Feature response
    """
    id: UUID
    layer_id: UUID
    type: str = "Feature"
    geometry: Dict[str, Any]  # Output as GeoJSON Dict
    properties: Dict[str, Any]

    class Config:
        from_attributes = True


class FeatureCollectionResponse(BaseModel):
    """
    Standard GeoJSON FeatureCollection response
    """
    type: str = "FeatureCollection"
    features: List[FeatureResponse]


class TileRequest(BaseModel):
    """
    Schema for MVT (Vector Tile) requests, aligned with tile_service XYZ pattern
    """
    z: int = Field(..., ge=0, le=24)
    x: int = Field(..., ge=0)
    y: int = Field(..., ge=0)
    layer_id: UUID
    buffer: int = Field(default=64, description="Pixel buffer for clipping")
    extent: int = Field(default=4096, description="MVT coordinate extent")


class MVTConfig(BaseModel):
    """
    Configuration for the MVT Rendering Engine
    """
    enable_clipping: bool = True
    simplification_tolerance: float = 0.1
    max_features_per_tile: int = 5000
