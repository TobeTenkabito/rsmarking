from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class RasterFieldCreate(BaseModel):
    field_name: str
    field_alias: Optional[str] = None
    field_type: str = Field(..., pattern="^(string|number|boolean|date)$")
    field_order: Optional[int] = 0
    is_required: Optional[bool] = False
    default_val: Optional[str] = None


class RasterFieldUpdate(BaseModel):
    field_alias: Optional[str] = None
    field_type: Optional[str] = Field(None, pattern="^(string|number|boolean|date)$")
    field_order: Optional[int] = None
    is_required: Optional[bool] = None
    default_val: Optional[str] = None


class RasterFieldOut(BaseModel):
    id: int
    raster_index_id: int
    field_name: str
    field_alias: Optional[str]
    field_type: str
    field_order: int
    is_required: bool
    is_system: bool
    default_val: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
