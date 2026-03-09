import uvicorn
from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List, Optional
from contextlib import asynccontextmanager
from sqlalchemy import text

from services.annotation_service.database import get_db, engine
from services.annotation_service.crud.feature import FeatureCRUD, LayerCRUD
from services.annotation_service.schemas.geojson import (
    FeatureCreate,
    FeatureUpdate,
    FeatureResponse,
    FeatureCollectionResponse,
    ProjectCreate,
    LayerCreate
)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Service lifecycle management.
    Ensures database connectivity and performs initial checks.
    """
    # Verify DB connection on startup
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"Critical Error: Database connection failed: {e}")
        raise e
    yield
    # Cleanup logic on shutdown
    await engine.dispose()

app = FastAPI(
    title="Annotation Service",
    description="Microservice for RS remote sensing vector data management",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 开发阶段可以先写 *
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.post(
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
    """
    Create a new spatial feature (Annotation) for a specific layer.
    Automatically validates geometry topology and stores in EPSG:4326.
    """
    crud = FeatureCRUD(db)
    try:
        db_feature = await crud.create(layer_id, feature_in)
        # Convert back to GeoJSON-ready format for response
        return await crud.get_by_id(db_feature.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get(
    "/layers/{layer_id}/features",
    response_model=FeatureCollectionResponse,
    tags=["Query"]
)
async def list_features_in_bbox(
    layer_id: UUID,
    minx: float = Query(..., description="Minimum X (Longitude)"),
    miny: float = Query(..., description="Minimum Y (Latitude)"),
    maxx: float = Query(..., description="Maximum X (Longitude)"),
    maxy: float = Query(..., description="Maximum Y (Latitude)"),
    db: AsyncSession = Depends(get_db)
):
    """
    Fetch features within a specific bounding box (BBOX).
    Utilizes PostGIS GIST spatial index for high performance.
    """
    crud = FeatureCRUD(db)
    features = await crud.find_by_bbox(layer_id, minx, miny, maxx, maxy)
    return {"type": "FeatureCollection", "features": features}


@app.get(
    "/features/{feature_id}",
    response_model=FeatureResponse,
    tags=["CRUD"]
)
async def get_feature(feature_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Retrieve details of a single spatial feature by its ID.
    """
    crud = FeatureCRUD(db)
    feature = await crud.get_by_id(feature_id)
    if not feature:
        raise HTTPException(status_code=404, detail="Feature not found")
    return feature

@app.patch(
    "/features/{feature_id}",
    response_model=FeatureResponse,
    tags=["CRUD"]
)
async def update_feature(
    feature_id: UUID,
    feature_in: FeatureUpdate,
    db: AsyncSession = Depends(get_db)
):
    """
    Partially update an existing feature's geometry or properties.
    """
    crud = FeatureCRUD(db)
    try:
        updated = await crud.update(feature_id, feature_in)
        if not updated:
            raise HTTPException(status_code=404, detail="Feature not found")
        return await crud.get_by_id(updated.id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.delete(
    "/features/{feature_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["CRUD"]
)
async def delete_feature(feature_id: UUID, db: AsyncSession = Depends(get_db)):
    """
    Permanently delete a spatial feature.
    """
    crud = FeatureCRUD(db)
    success = await crud.delete(feature_id)
    if not success:
        raise HTTPException(status_code=404, detail="Feature not found")
    return None

@app.post(
    "/layers/{layer_id}/bulk",
    status_code=status.HTTP_201_CREATED,
    tags=["AI Batch"]
)
async def bulk_create_features(
    layer_id: UUID,
    features_in: List[FeatureCreate],
    db: AsyncSession = Depends(get_db)
):
    """
    Batch insert endpoint for AI-generated extraction results.
    Optimized for high-volume data ingestion.
    """
    crud = FeatureCRUD(db)
    try:
        await crud.bulk_create(layer_id, features_in)
        return {"message": f"Successfully ingested {len(features_in)} features"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Bulk ingestion failed: {str(e)}")


@app.post("/projects", tags=["Management"])
async def create_project(project_in: ProjectCreate, db: AsyncSession = Depends(get_db)):
    crud = LayerCRUD(db)
    return await crud.create_project(project_in.name)


@app.get("/projects", tags=["Management"])
async def list_projects(db: AsyncSession = Depends(get_db)):
    crud = LayerCRUD(db)
    return await crud.get_projects()


@app.post("/projects/{project_id}/layers", tags=["Management"])
async def create_layer(project_id: UUID, layer_in: LayerCreate, db: AsyncSession = Depends(get_db)):
    crud = LayerCRUD(db)
    return await crud.create_layer(project_id, layer_in.name, layer_in.source_raster_index_id)


@app.get("/projects/{project_id}/layers", tags=["Management"])
async def list_layers(project_id: UUID, db: AsyncSession = Depends(get_db)):
    crud = LayerCRUD(db)
    return await crud.get_layers_by_project(project_id)


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
