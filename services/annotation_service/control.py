from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List

from services.annotation_service.database import get_db
from services.annotation_service.crud.feature import FeatureCRUD
from services.annotation_service.schemas.geojson import (
    FeatureCreate,
    FeatureUpdate,
    FeatureResponse,
    FeatureCollectionResponse
)

router = APIRouter(prefix="", tags=["Features"])


@router.post(
    "/layers/{layer_id}/features",
    response_model=FeatureResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["CRUD"]
)
async def create_feature(
    layer_id: UUID,
    feature_in: FeatureCreate,
    db: AsyncSession = Depends(get_db)
):
    crud = FeatureCRUD(db)
    try:
        db_feature = await crud.create(layer_id, feature_in)
        return await crud.get_by_id(db_feature.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get(
    "/layers/{layer_id}/features",
    response_model=FeatureCollectionResponse,
    tags=["Query"]
)
async def list_features_in_bbox(
    layer_id: UUID,
    minx: float = Query(..., description="Min X"),
    miny: float = Query(..., description="Min Y"),
    maxx: float = Query(..., description="Max X"),
    maxy: float = Query(..., description="Max Y"),
    db: AsyncSession = Depends(get_db)
):
    crud = FeatureCRUD(db)
    features = await crud.find_by_bbox(layer_id, minx, miny, maxx, maxy)
    return {"type": "FeatureCollection", "features": features}


@router.get("/features/{feature_id}", response_model=FeatureResponse, tags=["CRUD"])
async def get_feature(feature_id: UUID, db: AsyncSession = Depends(get_db)):
    crud = FeatureCRUD(db)
    feature = await crud.get_by_id(feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature


@router.patch("/features/{feature_id}", response_model=FeatureResponse, tags=["CRUD"])
async def update_feature(feature_id: UUID, feature_in: FeatureUpdate, db: AsyncSession = Depends(get_db)):
    crud = FeatureCRUD(db)
    try:
        updated = await crud.update(feature_id, feature_in)
        if not updated:
            raise HTTPException(status_code=404, detail="Feature not found")
        return await crud.get_by_id(updated.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/features/{feature_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["CRUD"])
async def delete_feature(feature_id: UUID, db: AsyncSession = Depends(get_db)):
    crud = FeatureCRUD(db)
    if not await crud.delete(feature_id):
        raise HTTPException(status_code=404, detail="Feature not found")
    return None


@router.post("/layers/{layer_id}/bulk", status_code=status.HTTP_201_CREATED, tags=["AI Batch"])
async def bulk_create_features(layer_id: UUID, features_in: List[FeatureCreate], db: AsyncSession = Depends(get_db)):
    crud = FeatureCRUD(db)
    try:
        await crud.bulk_create(layer_id, features_in)
        return {"message": f"Successfully ingested {len(features_in)} features"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk ingestion failed: {str(e)}")
