"""
GeoJSON asyncexporttask
─────────────────────────────────────────────────────────────────────────────
from annotation_service databaseread vector features,
serialize as standard GeoJSON FeatureCollection and write to file.
"""
import json
import logging
import os
from datetime import datetime, timezone
from uuid import UUID

from worker_cluster.app import celery_app
from worker_cluster.tasks.base import BaseRasterTask
from worker_cluster.bridge.db_sync import get_sync_db

logger = logging.getLogger("worker.export.geojson")

# export directory(can be overridden by environment variable)
EXPORT_DIR = os.getenv("EXPORT_DIR", "/storage/exports")


def _json_safe(value):
    if isinstance(value, UUID):
        return str(value)
    return value


def _geometry_from_row(value):
    if isinstance(value, str):
        return json.loads(value)
    return value


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
    export all vector features in the selected layer as GeoJSON text.

    Args:
        layer_id    : annotation_service text ID
        output_path : optional,specified output path;default writes to /storage/exports/
    Returns:
        {"output_path": ..., "feature_count": ...}
    """
    try:
        self.report(10, f"Reading features for layer {layer_id}")

        # directly connect to annotation_service database
        # note:annotation_service uses the same PostgreSQL text,different schema/table
        from sqlalchemy import text

        with get_sync_db() as db:
            result = db.execute(
                text("""
                    SELECT
                        f.id,
                        f.properties,
                        ST_AsGeoJSON(f.geom)::json AS geometry
                    FROM features f
                    WHERE f.layer_id = :layer_id
                    ORDER BY f.id
                """),
                {"layer_id": layer_id},
            )
            rows = result.fetchall()

        self.report(50, f"Serializing {len(rows)} features")

        features = []
        for row in rows:
            features.append({
                "type": "Feature",
                "id": _json_safe(row.id),
                "geometry": _geometry_from_row(row.geometry),
                "properties": row.properties or {},
            })

        collection = {
            "type": "FeatureCollection",
            "features": features,
            "metadata": {
                "layer_id": _json_safe(layer_id),
                "feature_count": len(features),
                "exported_at": datetime.now(timezone.utc).isoformat(),
            },
        }

        # Writing file
        if output_path is None:
            os.makedirs(EXPORT_DIR, exist_ok=True)
            output_path = os.path.join(
                EXPORT_DIR, f"layer_{layer_id}_{int(datetime.now().timestamp())}.geojson"
            )
        else:
            parent = os.path.dirname(os.path.abspath(output_path))
            if parent:
                os.makedirs(parent, exist_ok=True)

        self.report(80, "Writing file")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(collection, f, ensure_ascii=False, indent=2)

        logger.info(f"[export_geojson] done layer_id={layer_id} features={len(features)}")
        return {"output_path": output_path, "feature_count": len(features)}

    except Exception as exc:
        logger.exception(f"[export_geojson] failed layer_id={layer_id}")
        raise self.retry(exc=exc, countdown=15)
