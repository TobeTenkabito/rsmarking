from uuid import UUID
from typing import Optional, Literal
from pydantic import BaseModel, field_validator

# 允许的字段类型
FieldType = Literal["string", "number", "boolean", "date"]


class LayerFieldCreate(BaseModel):
    """用户手动新增一列"""
    field_name  : str
    field_alias : Optional[str] = None
    field_type  : FieldType = "string"
    field_order : Optional[int] = 0
    is_required : Optional[bool] = False
    default_val : Optional[str] = None

    @field_validator("field_name")
    @classmethod
    def name_no_space(cls, v: str) -> str:
        """field_name 作为 JSONB key，不允许空格"""
        if " " in v:
            raise ValueError("field_name 不能包含空格，请使用下划线")
        return v.lower()


class LayerFieldUpdate(BaseModel):
    """用户修改列定义（改别名、顺序等，不允许改 field_name）"""
    field_alias : Optional[str] = None
    field_type  : Optional[FieldType] = None
    field_order : Optional[int] = None
    is_required : Optional[bool] = None
    default_val : Optional[str] = None


class LayerFieldOut(BaseModel):
    """返回给前端的字段定义"""
    id          : UUID
    layer_id    : UUID
    field_name  : str
    field_alias : Optional[str]
    field_type  : FieldType
    field_order : int
    is_required : bool
    is_system   : bool
    default_val : Optional[str]

    model_config = {"from_attributes": True}


class LayerFieldIngest(BaseModel):
    """
    文件导入时内部使用，自动从文件属性生成字段定义。
    is_system=True，前端不可删除。
    """
    field_name  : str
    field_alias : Optional[str] = None
    field_type  : FieldType = "string"
    field_order : int = 0
    is_system   : bool = True