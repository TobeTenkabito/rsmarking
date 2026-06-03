from uuid import UUID
from typing import Optional, Literal
from pydantic import BaseModel, field_validator

# field type
FieldType = Literal["string", "number", "boolean", "date"]


class LayerFieldCreate(BaseModel):
    """manually add a column"""
    field_name: str
    field_alias: Optional[str] = None
    field_type: FieldType = "string"
    field_order: Optional[int] = 0
    is_required: Optional[bool] = False
    default_val: Optional[str] = None

    @field_validator("field_name")
    @classmethod
    def name_no_space(cls, v: str) -> str:
        """field_name text JSONB key,spaces are not allowed"""
        if " " in v:
            raise ValueError("field_name cannot contain spaces; use underscores")
        return v


class LayerFieldUpdate(BaseModel):
    """user updates column definitions(change alias,order,cannot change field_name)"""
    field_alias: Optional[str] = None
    field_type: Optional[FieldType] = None
    field_order: Optional[int] = None
    is_required: Optional[bool] = None
    default_val: Optional[str] = None


class LayerFieldOut(BaseModel):
    """field definitions returned to the frontend"""
    id: UUID
    layer_id: UUID
    field_name: str
    field_alias: Optional[str]
    field_type: FieldType
    field_order: int
    is_required: bool
    is_system: bool
    default_val: Optional[str]

    model_config = {"from_attributes": True}


class LayerFieldIngest(BaseModel):
    """
    used internally during file import,automatically generate field definitions from file properties.
    is_system=True,cannot be deleted by frontend.
    """
    field_name: str
    field_alias: Optional[str] = None
    field_type: FieldType = "string"
    field_order: int = 0
    is_system: bool = True
