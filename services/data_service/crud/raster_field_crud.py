from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from typing import List, Optional
from services.data_service.models import RasterField
from services.data_service.raster_field import RasterFieldCreate, RasterFieldUpdate
from sqlalchemy import update as sa_update

_PYTHON_TYPE_MAP = {
    str:   "string",
    int:   "number",
    float: "number",
    bool:  "boolean",
}


class RasterFieldCRUD:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def get_by_raster(self, raster_index_id: int) -> List[RasterField]:
        """获取某栅格的全部字段定义，按 field_order 排序"""
        result = await self.db.execute(
            select(RasterField)
            .where(RasterField.raster_index_id == raster_index_id)
            .order_by(RasterField.field_order)
        )
        return result.scalars().all()

    async def get_by_id(self, field_id: int) -> Optional[RasterField]:
        result = await self.db.execute(
            select(RasterField).where(RasterField.id == field_id)
        )
        return result.scalar_one_or_none()

    async def create(self, raster_index_id: int, schema: RasterFieldCreate) -> RasterField:
        """用户在前端点击「新增字段」时调用"""
        # 同一栅格内 field_name 不能重复
        existing = await self.db.execute(
            select(RasterField).where(
                RasterField.raster_index_id == raster_index_id,
                RasterField.field_name == schema.field_name
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"字段 '{schema.field_name}' 在该栅格中已存在")

        field = RasterField(
            raster_index_id = raster_index_id,
            field_name  = schema.field_name,
            field_alias = schema.field_alias or schema.field_name,
            field_type  = schema.field_type,
            field_order = schema.field_order,
            is_required = schema.is_required,
            is_system   = False,          # 用户手动创建，可删除
            default_val = schema.default_val,
        )
        self.db.add(field)
        await self.db.commit()
        await self.db.refresh(field)
        return field

    async def ingest_from_metadata(
        self,
        raster_index_id: int,
        metadata_dict: dict,
    ) -> List[RasterField]:
        """
        影像入库时自动调用，从 metadata_dict 推断字段写入 raster_fields。
        已存在的字段跳过（幂等）。
        系统字段示例：crs / bounds / resolution_x / resolution_y 等。
        """
        existing_result = await self.db.execute(
            select(RasterField.field_name)
            .where(RasterField.raster_index_id == raster_index_id)
        )
        existing_names = {row[0] for row in existing_result.fetchall()}

        fields_to_add = []
        for order, (key, value) in enumerate(metadata_dict.items()):
            if key in existing_names:
                continue
            py_type = type(value) if value is not None else str
            field_type = _PYTHON_TYPE_MAP.get(py_type, "string")
            fields_to_add.append(RasterField(
                raster_index_id = raster_index_id,
                field_name  = key,
                field_alias = key,
                field_type  = field_type,
                field_order = order,
                is_system   = True,       # 自动导入，前端标记为系统字段
            ))

        if fields_to_add:
            self.db.add_all(fields_to_add)
            await self.db.commit()

        return fields_to_add

    async def update(self, field_id: int, schema: RasterFieldUpdate) -> Optional[RasterField]:
        """修改别名、类型、顺序等，系统字段同样可修改显示属性"""
        field = await self.get_by_id(field_id)
        if not field:
            return None

        update_data = schema.model_dump(exclude_unset=True)
        if not update_data:
            return field

        await self.db.execute(
            sa_update(RasterField)
            .where(RasterField.id == field_id)
            .values(**update_data)
        )
        await self.db.commit()
        await self.db.refresh(field)
        return field

    async def delete(self, field_id: int) -> bool:
        """仅允许删除非系统字段"""
        field = await self.get_by_id(field_id)
        if not field:
            return False
        if field.is_system:
            raise ValueError(f"字段 '{field.field_name}' 为系统字段，不可删除")
        await self.db.delete(field)
        await self.db.commit()
        return True
