import os
import logging
import numpy as np
import rasterio
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, text

from services.data_service.crud import RasterCRUD
from services.annotation_service.crud.feature import LayerCRUD
from services.annotation_service.models.feature import Feature

from services.ai_gateway.schema_validator import (
    RasterContextData,
    VectorContextData,
    SpatialBounds,
    NumericStats
)

logger = logging.getLogger("ai_gateway.data_extractor")


def _compute_raster_stats(file_path: str) -> NumericStats | None:
    # 保持原有逻辑不变
    if not file_path or not os.path.exists(file_path):
        return None
    try:
        with rasterio.open(file_path) as src:
            factor = max(1, src.width // 512, src.height // 512)
            out_shape = (1, int(src.height / factor), int(src.width / factor))
            data = src.read(1, out_shape=out_shape)
            valid_data = data[data != src.nodata] if src.nodata is not None else data
            if valid_data.size == 0:
                return None

            min_val = float(np.min(valid_data))
            max_val = float(np.max(valid_data))
            mean_val = float(np.mean(valid_data))
            std_val = float(np.std(valid_data))

            hist, bin_edges = np.histogram(valid_data, bins=5)
            hist_dict = {f"{bin_edges[i]:.2f}-{bin_edges[i + 1]:.2f}": int(hist[i]) for i in range(5)}
            return NumericStats(min=min_val, max=max_val, mean=mean_val, std_dev=std_val, histogram=hist_dict)
    except Exception as e:
        logger.warning(f"提取栅格统计特征失败 ({file_path}): {e}")
        return None


async def _extract_raster_data(db: AsyncSession, raster_id: int) -> RasterContextData:
    # 保持原有逻辑不变
    raster = await RasterCRUD.get_raster_by_index_id(db, raster_id)
    if not raster:
        raise ValueError(f"未找到 index_id 为 {raster_id} 的栅格数据")

    b_data = raster.bounds or [0.0, 0.0, 0.0, 0.0]
    if isinstance(b_data, dict):
        xmin, ymin = b_data.get("xmin", 0.0), b_data.get("ymin", 0.0)
        xmax, ymax = b_data.get("xmax", 0.0), b_data.get("ymax", 0.0)
    else:
        xmin, ymin = b_data[0], b_data[1]
        xmax, ymax = b_data[2] if len(b_data) > 2 else b_data[0], b_data[3] if len(b_data) > 3 else b_data[1]

    c_data = raster.center or [0.0, 0.0]
    if isinstance(c_data, dict):
        cx, cy = c_data.get("x", 0.0), c_data.get("y", 0.0)
    else:
        cx, cy = c_data[0], c_data[1]

    stats = _compute_raster_stats(raster.file_path)

    return RasterContextData(
        name=raster.file_name or "unknown_raster", crs=raster.crs or "EPSG:4326",
        bounds=SpatialBounds(xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax),
        center={"x": cx, "y": cy}, width=raster.width, height=raster.height,
        bands_count=raster.bands or 1, data_type=raster.data_type or "unknown",
        resolution={"x": raster.resolution_x or 0.0, "y": raster.resolution_y or 0.0}, stats=stats
    )


async def _extract_vector_data(db: AsyncSession, layer_id: str) -> VectorContextData:
    # 保持原有逻辑不变
    layer_crud = LayerCRUD(db)
    layer = await layer_crud.get_layer(layer_id)
    if not layer:
        raise ValueError(f"未找到 id 为 {layer_id} 的矢量图层")

    stmt_stats = select(Feature.category, func.count(Feature.id)).where(Feature.layer_id == layer_id).group_by(Feature.category)
    result_stats = await db.execute(stmt_stats)
    distribution = {row[0] or "uncategorized": row[1] for row in result_stats.all()}
    total_features = sum(distribution.values())

    stmt_bounds = text("""
        SELECT ST_XMin(ST_Extent(geom)) as xmin, ST_YMin(ST_Extent(geom)) as ymin,
               ST_XMax(ST_Extent(geom)) as xmax, ST_YMax(ST_Extent(geom)) as ymax
        FROM features WHERE layer_id = :layer_id
    """)
    result_bounds = await db.execute(stmt_bounds, {"layer_id": layer_id})
    bounds_row = result_bounds.fetchone()

    bounds = SpatialBounds(xmin=bounds_row.xmin, ymin=bounds_row.ymin, xmax=bounds_row.xmax, ymax=bounds_row.ymax) if bounds_row and bounds_row.xmin is not None else SpatialBounds(xmin=-180.0, ymin=-90.0, xmax=180.0, ymax=90.0)

    stmt_schema = select(Feature.properties).where(Feature.layer_id == layer_id).limit(1)
    result_schema = await db.execute(stmt_schema)
    schema_row = result_schema.scalar_one_or_none()

    properties_schema, numeric_stats = {}, {}
    if schema_row:
        for k, v in schema_row.items():
            prop_type = type(v).__name__
            properties_schema[k] = prop_type
            if prop_type in ['int', 'float']:
                agg_stmt = text(f"""
                    SELECT MIN((properties->>'{k}')::numeric), MAX((properties->>'{k}')::numeric), AVG((properties->>'{k}')::numeric)
                    FROM features WHERE layer_id = :layer_id AND properties ? '{k}'
                """)
                agg_res = await db.execute(agg_stmt, {"layer_id": layer_id})
                agg_row = agg_res.fetchone()
                if agg_row and agg_row[0] is not None:
                    numeric_stats[k] = NumericStats(min=float(agg_row[0]), max=float(agg_row[1]), mean=float(agg_row[2]))

    return VectorContextData(
        name=layer.name, crs="EPSG:4326", bounds=bounds, feature_count=total_features,
        category_distribution=distribution, properties_schema=properties_schema, numeric_stats=numeric_stats
    )