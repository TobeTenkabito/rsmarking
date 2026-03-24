from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from services.annotation_service.database import get_db
from services.annotation_service.crud.layer_crud import LayerCRUD
from services.annotation_service.schemas.geojson import ProjectCreate, LayerCreate

router = APIRouter(tags=["Management"])


@router.post("/projects")
async def create_project(project_in: ProjectCreate, db: AsyncSession = Depends(get_db)):
    return await LayerCRUD(db).create_project(project_in.name)


@router.get("/projects")
async def list_projects(db: AsyncSession = Depends(get_db)):
    return await LayerCRUD(db).get_projects()


@router.post("/projects/{project_id}/layers")
async def create_layer(project_id: UUID, layer_in: LayerCreate, db: AsyncSession = Depends(get_db)):
    return await LayerCRUD(db).create_layer(project_id, layer_in.name, layer_in.source_raster_index_id)


@router.get("/projects/{project_id}/layers")
async def list_layers(project_id: UUID, db: AsyncSession = Depends(get_db)):
    return await LayerCRUD(db).get_layers_by_project(project_id)


@router.delete("/projects", status_code=204)
async def clear_all_projects(db: AsyncSession = Depends(get_db)):
    count = await LayerCRUD(db).delete_all_projects()
    return {"deleted_count": count}
