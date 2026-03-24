import uuid
from uuid import UUID
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete, update

from ..models.feature import LayerField
from ..schemas.layer_field import LayerFieldCreate, LayerFieldUpdate, LayerFieldIngest


# 文件属性类型 → LayerField.field_type 的映射
PYTHON_TYPE_MAP = {
    str  : "string",
    int  : "number",
    float: "number",
    bool : "boolean",
}


class LayerFieldCRUD:

    def __init__(self, db: AsyncSession):
        self.db = db


    async def get_by_layer(self, layer_id: UUID) -> List[LayerField]:
        """获取某图层的全部字段定义，按 field_order 排序"""
        result = await self.db.execute(
            select(LayerField)
            .where(LayerField.layer_id == layer_id)
            .order_by(LayerField.field_order)
        )
        return result.scalars().all()

    async def get_by_id(self, field_id: UUID) -> Optional[LayerField]:
        result = await self.db.execute(
            select(LayerField).where(LayerField.id == field_id)
        )
        return result.scalar_one_or_none()


    async def create(self, layer_id: UUID, schema: LayerFieldCreate) -> LayerField:
        """用户在前端点击「新增字段」时调用"""
        # 同一图层内 field_name 不能重复
        existing = await self.db.execute(
            select(LayerField).where(
                LayerField.layer_id == layer_id,
                LayerField.field_name == schema.field_name
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"字段 '{schema.field_name}' 在该图层中已存在")

        field = LayerField(
            id          = uuid.uuid4(),
            layer_id    = layer_id,
            field_name  = schema.field_name,
            field_alias = schema.field_alias or schema.field_name,
            field_type  = schema.field_type,
            field_order = schema.field_order,
            is_required = schema.is_required,
            is_system   = False,               # 用户手动创建，可删除
            default_val = schema.default_val,
        )
        self.db.add(field)
        await self.db.commit()
        await self.db.refresh(field)
        return field


    async def ingest_from_file(
        self,
        layer_id  : UUID,
        properties: dict,           # 文件第一个要素的 properties 原始字典
    ) -> List[LayerField]:
        """
        上传 shapefile / geojson 时自动调用。
        从文件属性推断字段名和类型，写入 layer_fields。
        已存在的字段跳过（幂等）。
        """
        existing_result = await self.db.execute(
            select(LayerField.field_name).where(LayerField.layer_id == layer_id)
        )
        existing_names = {row[0] for row in existing_result.fetchall()}

        fields_to_add = []
        for order, (key, value) in enumerate(properties.items()):
            if key in existing_names:
                continue
            # 推断类型
            py_type  = type(value) if value is not None else str
            field_type = PYTHON_TYPE_MAP.get(py_type, "string")

            fields_to_add.append(LayerField(
                id          = uuid.uuid4(),
                layer_id    = layer_id,
                field_name  = key,
                field_alias = key,             # 初始 alias = 原始字段名
                field_type  = field_type,
                field_order = order,
                is_system   = True,            # 文件来源，不可删除
                is_required = False,
            ))

        if fields_to_add:
            self.db.add_all(fields_to_add)
            await self.db.commit()

        return fields_to_add


    async def update(self, field_id: UUID, schema: LayerFieldUpdate) -> Optional[LayerField]:
        """修改别名、类型、顺序等，field_name 不可改"""
        field = await self.get_by_id(field_id)
        if not field:
            return None

        update_data = schema.model_dump(exclude_unset=True)
        for key, val in update_data.items():
            setattr(field, key, val)

        await self.db.commit()
        await self.db.refresh(field)
        return field


    async def delete(self, field_id: UUID) -> bool:
        """
        只允许删除 is_system=False 的字段。
        注意：删除字段定义不会清除 Feature.properties 里的历史数据，
        前端不再渲染该列即可，数据保留以防误删。
        """
        field = await self.get_by_id(field_id)
        if not field:
            return False
        if field.is_system:
            raise PermissionError("系统字段（文件导入）不可删除")

        await self.db.execute(
            delete(LayerField).where(LayerField.id == field_id)
        )
        await self.db.commit()
        return True