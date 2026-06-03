"""
context_builder.py
Build map context by formatting the current viewport, selected features, and related frontend state for the LLM prompt.
"""
import logging
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

logger = logging.getLogger("ai_gateway.context_builder")


class MapViewport(BaseModel):
    """Current map viewport"""
    zoom: Optional[float]   = Field(None, description="Current zoom level")
    center_lng: Optional[float] = Field(None, description="Viewport center longitude")
    center_lat: Optional[float] = Field(None, description="Viewport center latitude")
    bbox: Optional[List[float]] = Field(
        None,
        description="Current viewport bounding box [xmin, ymin, xmax, ymax]"
    )


class SelectedFeature(BaseModel):
    """Features selected by the user on the map"""
    feature_id: Optional[str]  = Field(None, description="Feature ID")
    layer_id:   Optional[str]  = Field(None, description="Owning layer ID")
    geometry_type: Optional[str] = Field(None, description="Geometry type")
    properties: Optional[Dict[str, Any]] = Field(None, description="Feature properties")


class MapContext(BaseModel):
    """Complete map context supplied by the frontend request"""
    viewport:          Optional[MapViewport]       = None
    selected_features: Optional[List[SelectedFeature]] = None
    active_layers:     Optional[List[str]]         = Field(
        None, description="List of currently visible layer IDs"
    )
    extra: Optional[Dict[str, Any]] = Field(
        None, description="Other custom frontend context"
    )

def build_map_context_prompt(ctx: Optional[MapContext]) -> str:
    """
    Convert map context into a natural-language description and inject it at the start of the LLM prompt.
    Return an empty string when no frontend context is supplied.
    """
    if ctx is None:
        return ""

    lines = ["[Current Map Context]"]

    # Viewport information
    if ctx.viewport:
        vp = ctx.viewport
        if vp.zoom is not None:
            lines.append(f"- Current zoom level: {vp.zoom}")
        if vp.center_lng is not None and vp.center_lat is not None:
            lines.append(f"- Viewport center: longitude {vp.center_lng:.4f}, latitude {vp.center_lat:.4f}")
        if vp.bbox:
            lines.append(
                f"- Viewport bounds: [{', '.join(f'{v:.4f}' for v in vp.bbox)}]"
            )

    # Selected features
    if ctx.selected_features:
        lines.append(f"- The user selected {len(ctx.selected_features)} features:")
        for feat in ctx.selected_features[:3]:   # Show at most 3 items to keep the prompt short
            desc = f"  · Feature ID={feat.feature_id or 'Unknown'}"
            if feat.geometry_type:
                desc += f", Geometry type={feat.geometry_type}"
            if feat.properties:
                # Only include the first 5 properties
                props_preview = dict(list(feat.properties.items())[:5])
                desc += f", properties={props_preview}"
            lines.append(desc)

    # Active layers
    if ctx.active_layers:
        lines.append(f"- Currently visible layers: {', '.join(ctx.active_layers[:10])}")

    # Extra context
    if ctx.extra:
        for k, v in ctx.extra.items():
            lines.append(f"- {k}: {v}")

    return "\n".join(lines)


def build_map_context(payload_extra: Optional[Dict[str, Any]]) -> str:
    """
    Parse MapContext from payload.extra and generate a prompt fragment.
    Called from analyze_handler / streaming_handler.

    Usage:
        map_ctx_str = build_map_context(payload.map_context)
    """
    if not payload_extra:
        return ""
    try:
        ctx = MapContext(**payload_extra)
        return build_map_context_prompt(ctx)
    except Exception as e:
        logger.warning(f"[ContextBuilder] Failed to parse map context; skipped: {e}")
        return ""
