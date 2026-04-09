"""
GeoJSON 异步导出任务
─────────────────────────────────────────────────────────────────────────────
从 annotation_service 的数据库中读取矢量要素，
序列化为标准 GeoJSON FeatureCollection 并写入文件。
"""
import json
import logging
import os
from datetime import datetime, timezone

from worker_cluster.app import celery_app
from worker_cluster.tasks.base import BaseRasterTask
from worker_cluster.bridge.db_sync import get_sync_db

logger = logging.getLogger("worker.export.geojson")

# 导出目录（可通过环境变量覆盖）
EXPORT_DIR = os.getenv("EXPORT_DIR", "/storage/exports")


@celery_app.task(
    bind=True,
    base=BaseRasterTask,
    name="worker_cluster.tasks.export.geojson",
    queue="export",
)
def export_geojson_task(
    self,
    layer_id: int,
    output_path: str | None = None,
) -> dict:
    """
    将指定图层的所有矢量要素导出为 GeoJSON 文件。

    Args:
        layer_id    : annotation_service 中的图层 ID
        output_path : 可选，指定输出路径；默认写到 /storage/exports/
    Returns:
        {"output_path": ..., "feature_count": ...}
    """
    try:
        self.report(10, f"读取图层 {layer_id} 的要素")

        # 直连 annotation_service 数据库
        # 注意：annotation_service 使用同一个 PostgreSQL 实例，不同 schema/表
        from sqlalchemy import text

        with get_sync_db() as db:
            result = db.execute(
                text("""
                    SELECT
                        f.id,
                        f.properties,
                        ST_AsGeoJSON(f.geometry)::json AS geometry
                    FROM features f
                    WHERE f.layer_id = :layer_id
                    ORDER BY f.id
                """),
                {"layer_id": layer_id},
            )
            rows = result.fetchall()

        self.report(50, f"序列化 {len(rows)} 个要素")

        features = []
        for row in rows:
            features.append({
                "type": "Feature",
                "id": row.id,
                "geometry": row.geometry,
                "properties": row.properties or {},
            })

        collection = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "layer_id": layer_id,
                "feature_count": len(features),
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        # 写出文件
        if output_path is None:
            os.makedirs(EXPORT_DIR, exist_ok=True)
            output_path = os.path.join(
                EXPORT_DIR, f"layer_{layer_id}_{int(datetime.now().timestamp())}.geojson"
            )

        self.report(80, "写出文件")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(collection, f, ensure_ascii=False, indent=2)

        logger.info(f"[export_geojson] done layer_id={layer_id} features={len(features)}")
        return {"output_path": output_path, "feature_count": len(features)}

    except Exception as exc:
        logger.exception(f"[export_geojson] failed layer_id={layer_id}")
        raise self.retry(exc=exc, countdown=15)
