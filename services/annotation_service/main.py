from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Union, Protocol
from uuid import UUID, uuid4
from dataclasses import dataclass, field
from datetime import datetime
from contextlib import asynccontextmanager

# GIS Standard libraries
from shapely.geometry import shape, mapping
from shapely.wkt import dumps, loads
from shapely.ops import transform
import pyproj
import json


# =============================================================================
# 1. DOMAIN LAYER (Entities & Value Objects)
# =============================================================================

@dataclass(frozen=True)
class GeometryValue:
    """
    Value Object for Spatial Data.
    Enforces WGS84 (4326) internally and handles SRID validation.
    """
    wkt: str
    srid: int = 4326

    def __post_init__(self):
        # 严格校验 SRID，目前架构仅支持 4326 存储
        if self.srid != 4326:
            raise ValueError(f"Unsupported SRID: {self.srid}. System core only accepts 4326.")

    def to_geojson(self) -> Dict:
        return mapping(loads(self.wkt))

    @classmethod
    def from_geojson(cls, geojson_dict: Dict, input_srid: int = 4326) -> "GeometryValue":
        """
        从 GeoJSON 转换，如果输入不是 4326，需在此处进行 Project。
        """
        geom = shape(geojson_dict)
        if not geom.is_valid:
            raise ValueError("Invalid geometry provided: Geometry is topologically incorrect.")

        # 如果前端传的是 3857 或其他坐标系，在此进行转换
        if input_srid != 4326:
            project = pyproj.Transformer.from_crs(f"EPSG:{input_srid}", "EPSG:4326", always_xy=True).transform
            geom = transform(project, geom)

        return cls(wkt=dumps(geom))


@dataclass
class Feature:
    id: UUID
    layer_id: UUID
    geometry: GeometryValue
    category: str
    properties: Dict[str, Any] = field(default_factory=dict)
    meta: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.utcnow)

    @classmethod
    def create(cls, layer_id: UUID, geometry: GeometryValue, category: str, **kwargs) -> "Feature":
        return cls(
            id=uuid4(),
            layer_id=layer_id,
            geometry=geometry,
            category=category,
            **kwargs
        )


# =============================================================================
# 2. REPOSITORY & UNIT OF WORK (Ports)
# =============================================================================

class FeatureRepository(ABC):
    @abstractmethod
    async def save(self, feature: Feature) -> None: pass

    @abstractmethod
    async def get_by_id(self, feature_id: UUID) -> Optional[Feature]: pass

    @abstractmethod
    async def find_by_bbox(self, layer_id: UUID, bbox: List[float]) -> List[Feature]: pass

    @abstractmethod
    async def get_mvt_tile(self, layer_id: UUID, z: int, x: int, y: int, buffer: int = 64) -> bytes: pass


class UnitOfWork(ABC):
    """
    UoW 模式保证事务原子性。
    """
    features: FeatureRepository

    @abstractmethod
    async def commit(self):
        pass

    @abstractmethod
    async def rollback(self):
        pass

    @asynccontextmanager
    async def transaction(self):
        try:
            yield self
            await self.commit()
        except Exception:
            await self.rollback()
            raise


# =============================================================================
# 3. APPLICATION LAYER (Use Cases)
# =============================================================================

class AnnotationUseCase:
    def __init__(self, uow: UnitOfWork):
        self.uow = uow

    async def create_annotation_from_geojson(self, layer_id: UUID, geojson: Dict) -> Feature:
        """
        使用 UoW 进行事务控制。
        """
        async with self.uow.transaction():
            geometry = GeometryValue.from_geojson(
                geojson.get("geometry", {}),
                input_srid=geojson.get("srid", 4326)
            )

            feature = Feature.create(
                layer_id=layer_id,
                geometry=geometry,
                category=geojson.get("properties", {}).get("category", "unclassified"),
                properties=geojson.get("properties", {}),
                meta={"source": "user_draw", "timestamp": datetime.utcnow().isoformat()}
            )

            await self.uow.features.save(feature)
            # 可以在此处执行其他 Repository 操作，如更新 Layer 统计信息
            return feature


# =============================================================================
# 4. INFRASTRUCTURE LAYER (PostGIS Implementation)
# =============================================================================

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text


class PostGISFeatureRepository(FeatureRepository):
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save(self, feature: Feature) -> None:
        # 实现具体的 SQLAlchemy 插入逻辑
        pass

    async def get_by_id(self, feature_id: UUID) -> Optional[Feature]:
        pass

    async def find_by_bbox(self, layer_id: UUID, bbox: List[float]) -> List[Feature]:
        pass

    async def get_mvt_tile(self, layer_id: UUID, z: int, x: int, y: int, buffer: int = 64) -> bytes:
        """
        支持 Clip 和 Buffer 的 MVT 生成逻辑。
        buffer=64 是标准值，防止瓦片边缘要素切断。
        """
        query = text("""
            WITH bounds AS (
                -- 获取瓦片的 3857 范围
                SELECT ST_TileEnvelope(:z, :x, :y) AS geom
            ),
            mvt_geom AS (
                SELECT 
                    -- ST_AsMVTGeom 第四个参数 clip_geom 默认为 true
                    ST_AsMVTGeom(
                        ST_Transform(f.geom, 3857), 
                        b.geom, 
                        4096,   -- 瓦片分辨率，默认 4096
                        :buffer, -- 缓冲区大小
                        true    -- clip_geom
                    ) AS geom,
                    f.category,
                    f.properties
                FROM features f, bounds b
                WHERE f.layer_id = :layer_id 
                -- 空间查询时需要考虑 buffer 扩展，避免漏掉跨瓦片要素
                AND f.geom && ST_Transform(ST_Expand(b.geom, :buffer_map_units), 4326)
            )
            SELECT ST_AsMVT(mvt_geom.*, 'default') FROM mvt_geom;
        """)
        # buffer_map_units 需要根据当前 z 缩放级别计算真实的 3857 单位距离
        pass


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory):
        self.session_factory = session_factory

    async def __aenter__(self):
        self.session = self.session_factory()
        self.features = PostGISFeatureRepository(self.session)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()

    async def commit(self):
        await self.session.commit()

    async def rollback(self):
        await self.session.rollback()
