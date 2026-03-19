from uuid import UUID
from typing import List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from ..models.feature import Project, Layer


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

    async def update_layer(self, layer_id: UUID, update_dict: dict) -> Optional[Layer]:
        """
        更新矢量图层元数据（仅更新传入的字段）
        用于 AI Modify 模式的"覆盖"分支
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
