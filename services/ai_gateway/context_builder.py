"""
context_builder.py
构建地图上下文 —— 将前端传入的当前视野、选中要素等信息格式化后注入 LLM Prompt。
"""
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_gateway.context_builder")


# ------------------------------------------------------------------
# 前端传入的地图上下文 Schema（扩展 AIRequestPayload 使用）
# ------------------------------------------------------------------

class MapViewport(BaseModel):
    """当前地图视野"""
    zoom: Optional[float]   = Field(None, description="当前缩放级别")
    center_lng: Optional[float] = Field(None, description="视野中心经度")
    center_lat: Optional[float] = Field(None, description="视野中心纬度")
    bbox: Optional[List[float]] = Field(
        None,
        description="当前视野边界框 [xmin, ymin, xmax, ymax]"
    )


class SelectedFeature(BaseModel):
    """用户在地图上选中的要素"""
    feature_id: Optional[str]  = Field(None, description="要素ID")
    layer_id:   Optional[str]  = Field(None, description="所属图层ID")
    geometry_type: Optional[str] = Field(None, description="几何类型")
    properties: Optional[Dict[str, Any]] = Field(None, description="要素属性")


class MapContext(BaseModel):
    """完整地图上下文（由前端在请求时附带）"""
    viewport:          Optional[MapViewport]       = None
    selected_features: Optional[List[SelectedFeature]] = None
    active_layers:     Optional[List[str]]         = Field(
        None, description="当前可见图层ID列表"
    )
    extra: Optional[Dict[str, Any]] = Field(
        None, description="其他前端自定义上下文"
    )


# ------------------------------------------------------------------
# 核心函数：将 MapContext 格式化为 Prompt 片段
# ------------------------------------------------------------------

def build_map_context_prompt(ctx: Optional[MapContext]) -> str:
    """
    将地图上下文转换为自然语言描述，注入 LLM Prompt 头部。
    若前端未传入上下文，返回空字符串（不影响主流程）。
    """
    if ctx is None:
        return ""

    lines = ["【当前地图操作上下文】"]

    # 视野信息
    if ctx.viewport:
        vp = ctx.viewport
        if vp.zoom is not None:
            lines.append(f"- 当前缩放级别: {vp.zoom}")
        if vp.center_lng is not None and vp.center_lat is not None:
            lines.append(f"- 视野中心: 经度 {vp.center_lng:.4f}, 纬度 {vp.center_lat:.4f}")
        if vp.bbox:
            lines.append(
                f"- 视野范围: [{', '.join(f'{v:.4f}' for v in vp.bbox)}]"
            )

    # 选中要素
    if ctx.selected_features:
        lines.append(f"- 用户已选中 {len(ctx.selected_features)} 个要素:")
        for feat in ctx.selected_features[:3]:   # 最多展示3个，防止 prompt 过长
            desc = f"  · 要素ID={feat.feature_id or '未知'}"
            if feat.geometry_type:
                desc += f", 几何类型={feat.geometry_type}"
            if feat.properties:
                # 只取前5个属性
                props_preview = dict(list(feat.properties.items())[:5])
                desc += f", 属性={props_preview}"
            lines.append(desc)

    # 活跃图层
    if ctx.active_layers:
        lines.append(f"- 当前可见图层: {', '.join(ctx.active_layers[:10])}")

    # 额外上下文
    if ctx.extra:
        for k, v in ctx.extra.items():
            lines.append(f"- {k}: {v}")

    return "\n".join(lines)


def build_map_context(payload_extra: Optional[Dict[str, Any]]) -> str:
    """
    从请求 payload 的 extra 字段中解析 MapContext 并生成 prompt 片段。
    在 analyze_handler / streaming_handler 中调用。

    用法：
        map_ctx_str = build_map_context(payload.map_context)
    """
    if not payload_extra:
        return ""
    try:
        ctx = MapContext(**payload_extra)
        return build_map_context_prompt(ctx)
    except Exception as e:
        logger.warning(f"[ContextBuilder] 解析地图上下文失败，已跳过: {e}")
        return ""
