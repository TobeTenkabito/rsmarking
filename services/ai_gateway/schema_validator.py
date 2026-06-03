import json
from enum import Enum
from typing import Dict, Any, Optional, Union
from pydantic import BaseModel, Field, field_validator, ValidationError


# ==========================================
# 1. Enum definitions (strictly limit frontend request parameters)
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
# 2. Basic spatial structures and deep statistics (strictly read-only)
# ==========================================

class SpatialBounds(BaseModel):
    """Spatial boundary definition"""
    xmin: float = Field(..., description="Minimum X coordinate (longitude)")
    ymin: float = Field(..., description="Minimum Y coordinate (latitude)")
    xmax: float = Field(..., description="Maximum X coordinate (longitude)")
    ymax: float = Field(..., description="Maximum Y coordinate (latitude)")

    @field_validator('xmax')
    def check_x_bounds(cls, v, info):
        if 'xmin' in info.data and v <= info.data['xmin']:
            raise ValueError("xmax must be greater than xmin")
        return v

    @field_validator('ymax')
    def check_y_bounds(cls, v, info):
        if 'ymin' in info.data and v <= info.data['ymin']:
            raise ValueError("ymax must be greater than ymin")
        return v


class NumericStats(BaseModel):
    """Level 2: deep statistics for numeric raster pixel values or vector attributes"""
    min: float = Field(..., description="Minimum value")
    max: float = Field(..., description="Maximum value")
    mean: float = Field(..., description="Mean value")
    std_dev: Optional[float] = Field(None, description="Standard deviation")
    histogram: Optional[Dict[str, int]] = Field(
        default=None,
        description="Data distribution histogram, for example {'0.00-0.20': 150, '0.20-0.40': 300}"
    )


# ==========================================
# 3. Modifiable data models (Tamper-resistant core: in MODIFY mode the AI can output only these fields)
# ==========================================

class RasterModifiable(BaseModel):
    """Fields the AI may modify for raster data"""
    name: str = Field(..., description="Display name of the raster layer (maps to database file_name)")
    # Reserved extension point for future AI-edited descriptions, default render styles, and similar fields.


class VectorModifiable(BaseModel):
    """Fields the AI may modify for vector data"""
    name: str = Field(..., description="Display name of the vector layer")
    # Reserved extension point for future AI-edited default category fields and similar fields.


# ==========================================
# 4. Complete context models (All information sent to the AI, extending the modifiable model)
# ==========================================

class RasterContextData(RasterModifiable):
    """Complete raster context"""
    crs: str = Field(..., description="Coordinate reference system, for example EPSG:4326")
    bounds: SpatialBounds = Field(..., description="Spatial bounds")
    center: Dict[str, float] = Field(..., description="Center coordinate containing x and y")
    resolution: Dict[str, float] = Field(..., description="Resolution containing x and y")
    bands_count: int = Field(..., description="Band count", ge=1)
    data_type: str = Field(..., description="Data type, such as Float32 or UInt8")

    # Expose additional low-level metadata for AI reference (read-only)
    file_path: Optional[str] = Field(None, description="Original file path (can be used to infer data source or format)")
    cog_path: Optional[str] = Field(None, description="Cloud Optimized GeoTIFF path status")
    bundle_id: Optional[int] = Field(None, description="Related tile package ID")

    stats: Optional[NumericStats] = Field(None, description="Statistics for raster pixel values")
    grid_sampling: Optional[Dict[str, Any]] = Field(
        None,
        description="Spatial grid sample data, including sample point distribution and pixel values"
    )


class VectorContextData(VectorModifiable):
    """Complete vector context"""
    crs: str = Field(..., description="Coordinate reference system, for example EPSG:4326")
    bounds: SpatialBounds = Field(..., description="Spatial bounds")
    feature_count: int = Field(..., description="Total feature count", ge=0)

    # Expose geometry type and data samples to help the AI understand the content
    primary_geometry_type: str = Field(default="Unknown", description="Primary geometry type of the layer (such as ST_Polygon or ST_Point)")
    sample_features: list[Dict[str, Any]] = Field(default_factory=list,
                                                  description="Up to 3 randomly sampled feature-property examples showing real data shape")

    category_distribution: Dict[str, int] = Field(default_factory=dict, description="Counts of features in each category")
    properties_schema: Dict[str, str] = Field(default_factory=dict, description="Attribute table fields and their data types")
    numeric_stats: Dict[str, NumericStats] = Field(default_factory=dict, description="Deep statistics for numeric fields in the attribute table")


# ==========================================
# 5. Business request and response models (API interaction layer)
# ==========================================

class AIRequestPayload(BaseModel):
    """Complete request body sent by the frontend to the AI gateway"""
    target_id: Union[int, str] = Field(..., description="Layer database ID (raster index_id or layer UUID)")
    data_type: DataType = Field(..., description="Data type: raster or vector")
    mode: TaskMode = Field(..., description="Task mode: analyze or modify")
    language: AILanguage = Field(default=AILanguage.EN, description="AI response language")
    user_prompt: str = Field(..., min_length=2, max_length=2000, description="User natural-language instruction")
    overwrite:   bool = Field(default=False, description="Whether to overwrite the original record; creates a new one by default. Set True only after explicit frontend user confirmation.")
    session_id: Optional[str] = Field(
        None,
        description="Session ID for multi-turn memory. Generated and maintained by the frontend; UUID4 is recommended."
    )
    map_context: Optional[Dict[str, Any]] = Field(
        None,
        description="Frontend map context (current viewport, selected features, and similar data), parsed by context_builder and injected into the prompt."
    )


class AIModifyResponse(BaseModel):
    """
    Strict structure expected from the AI by the interpreter in modify mode.
    """
    # Note: this is strictly limited to Modifiable types to prevent AI tampering with statistical data.
    modified_data: Union[RasterModifiable, VectorModifiable] = Field(
        ...,
        description="AI-modified data structure containing only fields allowed for modification"
    )
    explanation: str = Field(
        default="",
        description="Brief AI explanation for this modification, not written to the database and used only for logs or frontend hints."
    )


# ==========================================
# 6. Core interpreter validation function
# ==========================================

def validate_ai_json_output(raw_json_str: str, expected_type: DataType) -> Union[RasterModifiable, VectorModifiable]:
    """
    Core interpreter: convert untrusted JSON returned by the AI into a trusted Pydantic object.
    If the AI outputs Markdown markers, they are cleaned.
    If the AI attempts to output read-only fields such as bounds or stats, Pydantic ignores them automatically.
    """
    try:
        # 1. Clean possible Markdown code fences from AI output
        cleaned_str = raw_json_str.strip()
        if cleaned_str.startswith("```json"):
            cleaned_str = cleaned_str[7:]
        elif cleaned_str.startswith("```"):
            cleaned_str = cleaned_str[3:]

        if cleaned_str.endswith("```"):
            cleaned_str = cleaned_str[:-3]

        cleaned_str = cleaned_str.strip()

        # 2. Parse into a Python dictionary
        parsed_dict = json.loads(cleaned_str)

        # 3. Extract the modified_data level, supporting both direct data and modified_data wrappers.
        data_to_validate = parsed_dict.get("modified_data", parsed_dict)

        # 4. Strong type validation (Validate as Modifiable to provide structural tamper resistance)
        if expected_type == DataType.RASTER:
            validated_data = RasterModifiable(**data_to_validate)
        else:
            validated_data = VectorModifiable(**data_to_validate)

        return validated_data

    except json.JSONDecodeError as e:
        raise ValueError(f"AI returned invalid JSON: {str(e)}\nRaw response: {raw_json_str}")
    except ValidationError as e:
        # Pydantic reports exactly which field type or rule is invalid.
        raise ValueError(f"AI returned a JSON structure that does not meet database requirements: {e.json()}")
