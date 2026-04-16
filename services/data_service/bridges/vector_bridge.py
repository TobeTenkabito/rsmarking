import httpx
import logging
from typing import List, Dict, Any
from uuid import UUID
from fastapi import HTTPException

logger = logging.getLogger("data_service.executor_bridge")

ANNOTATION_SERVICE_URL = "http://localhost:8001"


async def internal_fetch_features(layer_id: UUID) -> List[Dict[str, Any]]:
    url = f"{ANNOTATION_SERVICE_URL}/layers/{layer_id}/features/export"
    async with httpx.AsyncClient(timeout=120.0) as client:
        try:
            response = await client.get(url)

            if response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"图层 {layer_id} 不存在")

            response.raise_for_status()
            data = response.json()

            # 强制规范化输出：确保始终返回 List[Dict]
            if isinstance(data, dict):
                if data.get("type") == "FeatureCollection":
                    return data.get("features", [])
                # 如果后端只返回了单个要素
                if data.get("type") == "Feature":
                    return [data]

            if isinstance(data, list):
                return data

            return []  # 兜底返回空列表

        except httpx.ReadTimeout:
            logger.error(f"获取矢量数据超时: {url}")
            raise HTTPException(status_code=504, detail="矢量服务响应超时，数据量可能过大")
        except Exception as e:
            logger.error(f"内部通讯故障: {str(e)}")
            raise HTTPException(status_code=500, detail=f"无法获取矢量数据: {str(e)}")
