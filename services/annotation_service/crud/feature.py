import json
import uuid
from uuid import UUID
from typing import List, Optional, Dict, Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, func, text
from sqlalchemy.dialects.postgresql import insert
from geoalchemy2.functions import ST_AsGeoJSON, ST_GeomFromText, ST_MakeEnvelope
from shapely.geometry import shape, mapping
from shapely.wkt import dumps

from ..models.feature import Feature, Project, Layer
from ..schemas.geojson import FeatureCreate, FeatureUpdate


class FeatureCRUD:
    """
    CRUD implementation for Spatial Features.
    Focuses on PostGIS integration and GeoJSON compatibility.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(self, layer_id: UUID, schema: FeatureCreate) -> Feature:
        """
        Create a single feature with spatial validation and SRID handling.
        """
        # Convert GeoJSON geometry to WKT for PostGIS ingestion
        geom_obj = shape(schema.geometry.model_dump())
        if not geom_obj.is_valid:
            raise ValueError("Invalid topology: The provided geometry is not valid.")

        # We store as EWKT to ensure SRID 4326 is preserved
        wkt_geom = f"SRID=4326;{dumps(geom_obj)}"

        db_feature = Feature(
            layer_id=layer_id,
            geom=wkt_geom,
            category=schema.category or schema.properties.get("category", "default"),
            properties=schema.properties,
            meta={"created_at_srid": schema.srid}
        )

        self.db.add(db_feature)
        await self.db.commit()
        await self.db.refresh(db_feature)
        return db_feature

    async def get_by_id(self, feature_id: UUID) -> Optional[Dict[str, Any]]:
        """
        Retrieve a single feature and return as GeoJSON-ready dictionary.
        """
        query = select(
            Feature.id,
            Feature.layer_id,
            Feature.category,
            Feature.properties,
            ST_AsGeoJSON(Feature.geom).label("geometry_json")
        ).where(Feature.id == feature_id)

        result = await self.db.execute(query)
        row = result.fetchone()

        if not row:
            return None

        return {
            "id": row.id,
            "layer_id": row.layer_id,
            "type": "Feature",
            "geometry": json.loads(row.geometry_json),
            "properties": {**row.properties, "category": row.category}
        }

    async def find_by_bbox(self, layer_id: UUID, minx: float, miny: float, maxx: float, maxy: float) -> List[
        Dict[str, Any]]:
        """
        Fetch features within a specific bounding box using GIST spatial index.
        """
        query = select(
            Feature.id,
            Feature.layer_id,
            Feature.category,
            Feature.properties,
            ST_AsGeoJSON(Feature.geom).label("geometry_json")
        ).where(
            Feature.layer_id == layer_id,
            Feature.geom.intersects(ST_MakeEnvelope(minx, miny, maxx, maxy, 4326))
        )

        result = await self.db.execute(query)
        features = []
        for row in result:
            features.append({
                "id": row.id,
                "layer_id": row.layer_id,
                "type": "Feature",
                "geometry": json.loads(row.geometry_json),
                "properties": {**row.properties, "category": row.category}
            })
        return features

    async def update(self, feature_id: UUID, schema: FeatureUpdate) -> Optional[Feature]:
        """
        Update feature properties or spatial geometry.
        """
        query = select(Feature).where(Feature.id == feature_id)
        result = await self.db.execute(query)
        db_feature = result.scalar_one_or_none()

        if not db_feature:
            return None

        if schema.geometry:
            geom_obj = shape(schema.geometry.model_dump())
            if not geom_obj.is_valid:
                raise ValueError("Updated geometry is invalid.")
            db_feature.geom = f"SRID=4326;{dumps(geom_obj)}"

        if schema.properties is not None:
            # Merge JSONB properties
            db_feature.properties = {**db_feature.properties, **schema.properties}

        if schema.category:
            db_feature.category = schema.category

        await self.db.commit()
        await self.db.refresh(db_feature)
        return db_feature

    async def delete(self, feature_id: UUID) -> bool:
        """
        Delete a feature from the database.
        """
        query = delete(Feature).where(Feature.id == feature_id)
        result = await self.db.execute(query)
        await self.db.commit()
        return result.rowcount > 0

    async def bulk_create(self, layer_id: UUID, schemas: List[FeatureCreate]):
        """
        Batch insert features. Crucial for AI-assisted extraction results.
        """
        if not schemas:
            return

        data_to_insert = []
        for s in schemas:
            geom_wkt = dumps(shape(s.geometry.model_dump()))
            data_to_insert.append({
                "id": uuid.uuid4(),
                "layer_id": layer_id,
                "geom": f"SRID=4326;{geom_wkt}",
                "category": s.category or s.properties.get("category"),
                "properties": s.properties,
            })

        await self.db.execute(insert(Feature).values(data_to_insert))
        await self.db.commit()


class LayerCRUD:
    def __init__(self, db: AsyncSession):
        self.db = db

    # --- Project Operations ---
    async def create_project(self, name: str) -> Project:
        project = Project(name=name)
        self.db.add(project)
        await self.db.commit()
        await self.db.refresh(project)
        return project

    async def get_projects(self) -> List[Project]:
        result = await self.db.execute(select(Project))
        return result.scalars().all()

    # --- Layer Operations ---
    async def create_layer(self, project_id: UUID, name: str, source_index_id: Optional[int] = None) -> Layer:
        """
        创建图层，并可选地关联一个遥感影像 index_id
        """
        layer = Layer(
            project_id=project_id,
            name=name,
            source_raster_index_id=source_index_id
        )
        self.db.add(layer)
        await self.db.commit()
        await self.db.refresh(layer)
        return layer

    async def get_layers_by_project(self, project_id: UUID) -> List[Layer]:
        result = await self.db.execute(select(Layer).where(Layer.project_id == project_id))
        return result.scalars().all()

    async def get_layer(self, layer_id: UUID) -> Optional[Layer]:
        result = await self.db.execute(select(Layer).where(Layer.id == layer_id))
        return result.scalar_one_or_none()

    async def delete_all_projects(self):
        """
        清空所有项目及其关联数据
        由于模型中定义了 ForeignKey(ondelete="CASCADE")，
        数据库会自动清理 layers 和 features 表。
        """
        stmt = delete(Project)
        result = await self.db.execute(stmt)
        await self.db.commit()
        return result.rowcount  # 返回删除的记录数
