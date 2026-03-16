import json
from enum import Enum
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field, field_validator, ValidationError


# ==========================================
# 1. 枚举定义 (严格限制前端传入的参数)
# ==========================================

class AILanguage(str, Enum):
    ZH = "zh"
    EN = "en"
    JA = "ja"


class TaskMode(str, Enum):
    ANALYZE = "analyze"
    MODIFY = "modify"


class DataType(str, Enum):
    RASTER = "raster"
    VECTOR = "vector"


# ==========================================
# 2. 基础空间结构与深度统计特征 (绝对只读)
# ==========================================

class SpatialBounds(BaseModel):
    """空间边界定义"""
    xmin: float = Field(..., description="最小 X 坐标 (经度)")
    ymin: float = Field(..., description="最小 Y 坐标 (纬度)")
    xmax: float = Field(..., description="最大 X 坐标 (经度)")
    ymax: float = Field(..., description="最大 Y 坐标 (纬度)")

    @field_validator('xmax')
    def check_x_bounds(cls, v, info):
        if 'xmin' in info.data and v <= info.data['xmin']:
            raise ValueError("xmax 必须大于 xmin")
        return v

    @field_validator('ymax')
    def check_y_bounds(cls, v, info):
        if 'ymin' in info.data and v <= info.data['ymin']:
            raise ValueError("ymax 必须大于 ymin")
        return v


class NumericStats(BaseModel):
    """Level 2: 数值型数据的深度统计特征 (用于栅格像素值或矢量属性数值)"""
    min: float = Field(..., description="最小值")
    max: float = Field(..., description="最大值")
    mean: float = Field(..., description="平均值")
    std_dev: Optional[float] = Field(None, description="标准差")
    histogram: Optional[Dict[str, int]] = Field(
        default=None,
        description="数据分布直方图，例如 {'0.00-0.20': 150, '0.20-0.40': 300}"
    )


# ==========================================
# 3. 可修改数据模型 (防篡改核心：AI 在 MODIFY 模式下只能输出这些)
# ==========================================

class RasterModifiable(BaseModel):
    """栅格数据中允许 AI 修改的字段"""
    name: str = Field(..., description="栅格图层的显示名称 (对应数据库的 file_name)")
    # 预留扩展：如果未来允许 AI 修改描述、默认渲染样式等，加在这里


class VectorModifiable(BaseModel):
    """矢量数据中允许 AI 修改的字段"""
    name: str = Field(..., description="矢量图层的显示名称")
    # 预留扩展：如果未来允许 AI 修改默认分类字段等，加在这里


# ==========================================
# 4. 完整上下文模型 (发给 AI 阅读的全部信息，继承自可修改模型)
# ==========================================

class RasterContextData(RasterModifiable):
    """
    栅格完整上下文 (提取自 models.py 中的 RasterMetadata)
    发给 AI 进行分析的完整 JSON 实体。
    """
    crs: str = Field(..., description="坐标参考系统，例如 EPSG:4326")
    bounds: SpatialBounds = Field(..., description="空间边界")
    center: Dict[str, float] = Field(..., description="中心点坐标，包含 x 和 y")
    resolution: Dict[str, float] = Field(..., description="分辨率，包含 x 和 y")
    bands_count: int = Field(..., description="波段数量", ge=1)
    data_type: str = Field(..., description="数据类型，如 Float32, UInt8")

    # 深度统计特征
    stats: Optional[NumericStats] = Field(None, description="栅格像素值的统计特征")


class VectorContextData(VectorModifiable):
    """
    矢量完整上下文 (提取自 feature.py 中的 Layer/Feature)
    发给 AI 进行分析的完整 JSON 实体。
    """
    crs: str = Field(..., description="坐标参考系统，例如 EPSG:4326")
    bounds: SpatialBounds = Field(..., description="空间边界")
    feature_count: int = Field(..., description="要素总数", ge=0)
    category_distribution: Dict[str, int] = Field(default_factory=dict, description="各类别要素的数量统计")
    properties_schema: Dict[str, str] = Field(default_factory=dict, description="属性表字段及其数据类型")

    # 深度统计特征
    numeric_stats: Dict[str, NumericStats] = Field(
        default_factory=dict,
        description="属性表中数值型字段的深度统计特征 (极值、均值等)"
    )


# ==========================================
# 5. 业务请求与响应模型 (API 交互层)
# ==========================================

class AIRequestPayload(BaseModel):
    """前端发给 AI 网关的完整请求体"""
    target_id: Union[int, str] = Field(..., description="图层的数据库 ID (Raster index_id 或 Layer UUID)")
    data_type: DataType = Field(..., description="数据类型：raster 或 vector")
    mode: TaskMode = Field(..., description="任务模式：analyze (分析) 或 modify (修改)")
    language: AILanguage = Field(default=AILanguage.ZH, description="AI 响应语言")
    user_prompt: str = Field(..., min_length=2, max_length=2000, description="用户的自然语言指令")
    overwrite:   bool = Field(default=False, description="是否覆盖原始记录，默认新建。需前端用户手动确认后置为 True")


class AIModifyResponse(BaseModel):
    """
    修改模式下，解译器期望从 AI 接收的严格结构。
    """
    # 注意：这里严格限制为 Modifiable 类型，彻底阻断 AI 篡改统计数据的可能
    modified_data: Union[RasterModifiable, VectorModifiable] = Field(
        ...,
        description="AI 修改后的数据结构，只能包含允许修改的字段"
    )
    explanation: str = Field(
        default="",
        description="AI 对本次修改的简短说明（不写入数据库，仅供日志或前端提示）"
    )


# ==========================================
# 6. 核心解译器校验函数
# ==========================================

def validate_ai_json_output(raw_json_str: str, expected_type: DataType) -> Union[RasterModifiable, VectorModifiable]:
    """
    核心解译器：将 AI 返回的不可信 JSON 字符串转换为受信任的 Pydantic 对象。
    如果 AI 输出了 Markdown 标记，会进行清洗。
    如果 AI 试图输出 bounds 或 stats 等只读字段，Pydantic 会自动忽略它们。
    """
    try:
        # 1. 清洗 AI 可能带有的 Markdown 代码块标记
        cleaned_str = raw_json_str.strip()
        if cleaned_str.startswith("```json"):
            cleaned_str = cleaned_str[7:]
        elif cleaned_str.startswith("```"):
            cleaned_str = cleaned_str[3:]

        if cleaned_str.endswith("```"):
            cleaned_str = cleaned_str[:-3]

        cleaned_str = cleaned_str.strip()

        # 2. 解析为 Python 字典
        parsed_dict = json.loads(cleaned_str)

        # 3. 提取 modified_data 层级 (兼容 AI 直接返回数据或包装在 modified_data 中)
        data_to_validate = parsed_dict.get("modified_data", parsed_dict)

        # 4. 强类型校验 (强制校验为 Modifiable，实现物理防篡改)
        if expected_type == DataType.RASTER:
            validated_data = RasterModifiable(**data_to_validate)
        else:
            validated_data = VectorModifiable(**data_to_validate)

        return validated_data

    except json.JSONDecodeError as e:
        raise ValueError(f"AI 返回的不是合法的 JSON 格式: {str(e)}\n原始返回: {raw_json_str}")
    except ValidationError as e:
        # Pydantic 会精确指出哪个字段的类型或规则错了
        raise ValueError(f"AI 返回的 JSON 结构不符合数据库要求: {e.json()}")
