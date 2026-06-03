import httpx
import logging
from typing import List, Dict, Any
from uuid import UUID
from fastapi import HTTPException

logger = logging.getLogger("data_service.executor_bridge")

ANNOTATION_SERVICE_URL = "http://localhost:8001"


async def internal_create_layer(
    project_id: UUID,
    name: str,
    source_raster_index_id: int | None = None,
) -> Dict[str, Any]:
    url = f"{ANNOTATION_SERVICE_URL}/projects/{project_id}/layers"
    payload = {
        "name": name,
        "source_raster_index_id": source_raster_index_id,
    }
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            return response.json()
        except httpx.HTTPStatusError as e:
            detail = e.response.json().get("detail", e.response.text)
            raise HTTPException(status_code=e.response.status_code, detail=detail)
        except Exception as e:
            logger.error(f"Failed to create vector layer through annotation service: {e}")
            raise HTTPException(status_code=500, detail=f"Unable to create vector layer: {e}")


async def internal_create_fields(
    layer_id: UUID | str,
    fields: List[Dict[str, Any]],
) -> None:
    url = f"{ANNOTATION_SERVICE_URL}/{layer_id}/fields"
    async with httpx.AsyncClient(timeout=120.0) as client:
        for field in fields:
            try:
                response = await client.post(url, json=field)
                if response.status_code == 400:
                    detail = response.json().get("detail", "")
                    if "already" in detail.lower():
                        continue
                response.raise_for_status()
            except httpx.HTTPStatusError as e:
                detail = e.response.json().get("detail", e.response.text)
                raise HTTPException(status_code=e.response.status_code, detail=detail)
            except Exception as e:
                logger.error(f"Failed to create vector field through annotation service: {e}")
                raise HTTPException(status_code=500, detail=f"Unable to create vector field: {e}")


async def internal_bulk_create_features(
    layer_id: UUID | str,
    features: List[Dict[str, Any]],
) -> int:
    url = f"{ANNOTATION_SERVICE_URL}/layers/{layer_id}/bulk"
    payload = [
        {
            "geometry": feature["geometry"],
            "properties": feature.get("properties", {}),
            "category": feature.get("properties", {}).get("category", "raster_vectorized"),
            "srid": 4326,
        }
        for feature in features
    ]
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
            return data.get("imported", len(features))
        except httpx.HTTPStatusError as e:
            detail = e.response.json().get("detail", e.response.text)
            raise HTTPException(status_code=e.response.status_code, detail=detail)
        except Exception as e:
            logger.error(f"Failed to bulk create vector features through annotation service: {e}")
            raise HTTPException(status_code=500, detail=f"Unable to create vector features: {e}")


async def internal_fetch_features(layer_id: UUID) -> List[Dict[str, Any]]:
    url = f"{ANNOTATION_SERVICE_URL}/layers/{layer_id}/features/export"
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.get(url)

            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Layer {layer_id} does not exist")

            response.raise_for_status()
            data = response.json()

            # force normalized output:ensure it always returns List[Dict]
            if isinstance(data, dict):
                if data.get("type") == "FeatureCollection":
                    return data.get("features", [])
                # if the backend returned a single feature
                if data.get("type") == "Feature":
                    return [data]

            if isinstance(data, list):
                return data

            return []  # fallback to an empty list

        except httpx.ReadTimeout:
            logger.error(f"Fetching vector data timed out: {url}")
            raise HTTPException(status_code=504, detail="Vector service response timed out; the dataset may be too large")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Internal communication failure: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Unable to fetch vector data: {str(e)}")


async def internal_fetch_fields(layer_id: UUID | str) -> List[Dict[str, Any]]:
    url = f"{ANNOTATION_SERVICE_URL}/{layer_id}/fields"
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.get(url)

            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Layer {layer_id} does not exist")

            response.raise_for_status()
            data = response.json()
            return data if isinstance(data, list) else []

        except httpx.ReadTimeout:
            logger.error(f"Fetching vector fields timed out: {url}")
            raise HTTPException(status_code=504, detail="Vector field service response timed out")
        except HTTPException:
            raise
        except httpx.HTTPStatusError as e:
            detail = e.response.json().get("detail", e.response.text)
            raise HTTPException(status_code=e.response.status_code, detail=detail)
        except Exception as e:
            logger.error(f"textInternal communication failure: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Unable to fetch vector fields: {str(e)}")
