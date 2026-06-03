from uuid import UUID
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from ..models.feature import Feature, Layer, LayerField, Project


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
        create layer,and optionally link remote-sensing imagery index_id
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
        clear all projects and related data
        delete explicitly in dependency order,avoid old database constraints missing ON DELETE CASCADE when
        leaving layer_fields / features / layers.
        """
        field_result = await self.db.execute(delete(LayerField))
        feature_result = await self.db.execute(delete(Feature))
        layer_result = await self.db.execute(delete(Layer))
        project_result = await self.db.execute(delete(Project))
        await self.db.commit()
        return {
            "projects": project_result.rowcount or 0,
            "layers": layer_result.rowcount or 0,
            "features": feature_result.rowcount or 0,
            "fields": field_result.rowcount or 0,
        }

    async def update_layer(self, layer_id: UUID, update_dict: dict) -> Optional[Layer]:
        """
        update vector layer metadata(only update provided fields)
        used for AI Modify text"overwrite"branch
        """
        result = await self.db.execute(select(Layer).where(Layer.id == layer_id))
        layer = result.scalar_one_or_none()

        if not layer:
            return None

        for key, value in update_dict.items():
            if hasattr(layer, key):
                setattr(layer, key, value)

        await self.db.commit()
        await self.db.refresh(layer)
        return layer

    async def delete_layer(self, layer_id: UUID):
        result = await self.db.execute(delete(Layer).where(Layer.id == layer_id))
        await self.db.commit()
        return result.rowcount > 0
