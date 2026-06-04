import json
import logging
from typing import Any, Literal

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

import services.data_service.db_ops as db_ops
from services.data_service.database import get_db


logger = logging.getLogger("data_service.classification")
router = APIRouter()


@router.post("/classify-supervised")
async def classify_supervised(
    raster_id: int = Form(...),
    samples: str = Form(...),
    classifier: Literal["nearest_centroid", "random_forest", "svm"] = Form("nearest_centroid"),
    new_name: str = Form(...),
    band_indices: str | None = Form(None),
    n_estimators: int = Form(100),
    random_seed: int = Form(13),
    smoothing: int = Form(0),
    db: AsyncSession = Depends(get_db),
):
    return await db_ops.process_supervised_classification_task(
        db=db,
        raster_id=raster_id,
        samples=_parse_json_list(samples, "samples"),
        classifier=classifier,
        new_name=new_name,
        band_indices=_parse_int_list(band_indices),
        n_estimators=n_estimators,
        random_seed=random_seed,
        smoothing=smoothing,
    )


@router.post("/classify-unsupervised")
async def classify_unsupervised(
    raster_id: int = Form(...),
    n_classes: int = Form(5),
    method: Literal["kmeans", "mini_batch_kmeans"] = Form("kmeans"),
    new_name: str = Form(...),
    band_indices: str | None = Form(None),
    max_samples: int = Form(50000),
    random_seed: int = Form(13),
    smoothing: int = Form(0),
    db: AsyncSession = Depends(get_db),
):
    return await db_ops.process_unsupervised_classification_task(
        db=db,
        raster_id=raster_id,
        n_classes=n_classes,
        method=method,
        new_name=new_name,
        band_indices=_parse_int_list(band_indices),
        max_samples=max_samples,
        random_seed=random_seed,
        smoothing=smoothing,
    )


@router.post("/segment-deep-learning")
async def segment_deep_learning(
    raster_id: int = Form(...),
    new_name: str = Form(...),
    model_path: str | None = Form(None),
    backend: Literal["auto", "onnx", "spectral_spatial", "slic", "watershed"] = Form("auto"),
    n_classes: int = Form(2),
    band_indices: str | None = Form(None),
    threshold: float = Form(0.5),
    random_seed: int = Form(13),
    max_samples: int = Form(50000),
    compactness: float = Form(0.15),
    smoothing: int = Form(1),
    db: AsyncSession = Depends(get_db),
):
    return await db_ops.process_deep_learning_segmentation_task(
        db=db,
        raster_id=raster_id,
        new_name=new_name,
        model_path=model_path,
        backend=backend,
        n_classes=n_classes,
        band_indices=_parse_int_list(band_indices),
        threshold=threshold,
        random_seed=random_seed,
        max_samples=max_samples,
        compactness=compactness,
        smoothing=smoothing,
    )


def _parse_json_list(value: str, field_name: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=400, detail=f"{field_name} must be valid JSON: {exc}") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, dict) for item in parsed):
        raise HTTPException(status_code=400, detail=f"{field_name} must be a JSON array of objects")
    return parsed


def _parse_int_list(value: str | None) -> list[int] | None:
    if not value:
        return None
    try:
        if value.strip().startswith("["):
            parsed = json.loads(value)
            if not isinstance(parsed, list):
                raise ValueError
            return [int(item) for item in parsed]
        return [int(item.strip()) for item in value.split(",") if item.strip()]
    except Exception as exc:
        raise HTTPException(status_code=400, detail="band_indices must be a comma list or JSON integer array") from exc
