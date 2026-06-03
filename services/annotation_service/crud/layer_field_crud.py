import uuid
from uuid import UUID
from typing import List, Optional

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from ..models.feature import LayerField
from ..schemas.layer_field import LayerFieldCreate, LayerFieldUpdate


PYTHON_TYPE_MAP = {
    str: "string",
    int: "number",
    float: "number",
    bool: "boolean",
}


class LayerFieldCRUD:

    def __init__(self, db: AsyncSession):
        self.db = db


    async def get_by_layer(self, layer_id: UUID) -> List[LayerField]:
        """get all field definitions for a layer,by field_order sort"""
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
        """called when the user clicks"Add Field"text"""
        # within the same layer field_name cannot be duplicated
        existing = await self.db.execute(
            select(LayerField).where(
                LayerField.layer_id == layer_id,
                LayerField.field_name == schema.field_name
            )
        )
        if existing.scalar_one_or_none():
            raise ValueError(f"Field '{schema.field_name}' already exists in this layer")

        field = LayerField(
            id          = uuid.uuid4(),
            layer_id    = layer_id,
            field_name  = schema.field_name,
            field_alias = schema.field_alias or schema.field_name,
            field_type  = schema.field_type,
            field_order = schema.field_order,
            is_required = schema.is_required,
            is_system   = False,               # user-created,deletable
            default_val = schema.default_val,
        )
        self.db.add(field)
        await self.db.commit()
        await self.db.refresh(field)
        return field


    async def ingest_from_file(
        self,
        layer_id  : UUID,
        properties: dict,           # first feature in the file properties source dictionary
    ) -> List[LayerField]:
        """
        upload shapefile / geojson called automatically.
        infer field names and types from file properties,write layer_fields.
        skip existing fields(idempotent).
        """
        existing_result = await self.db.execute(
            select(LayerField.field_name).where(LayerField.layer_id == layer_id)
        )
        existing_names = {row[0] for row in existing_result.fetchall()}

        fields_to_add = []
        for order, (key, value) in enumerate(properties.items()):
            if key in existing_names:
                continue
            # infer type
            py_type  = type(value) if value is not None else str
            field_type = PYTHON_TYPE_MAP.get(py_type, "string")

            fields_to_add.append(LayerField(
                id          = uuid.uuid4(),
                layer_id    = layer_id,
                field_name  = key,
                field_alias = key,             # initial alias = text
                field_type  = field_type,
                field_order = order,
                is_system   = True,            # file source,not deletable
                is_required = False,
            ))

        if fields_to_add:
            self.db.add_all(fields_to_add)
            await self.db.commit()

        return fields_to_add


    async def update(self, field_id: UUID, schema: LayerFieldUpdate) -> Optional[LayerField]:
        """update alias,text,order,field_name text"""
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
        only allow deleting is_system=False text.
        note:deleting a field definition does not clear Feature.properties historical data in,
        only stop rendering the column,data is retained to avoid accidental deletion.
        """
        field = await self.get_by_id(field_id)
        if not field:
            return False
        if field.is_system:
            raise PermissionError("System fields imported from files cannot be deleted")

        await self.db.execute(
            delete(LayerField).where(LayerField.id == field_id)
        )
        await self.db.commit()
        return True
