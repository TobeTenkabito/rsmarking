from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from uuid import UUID
from typing import List
from fastapi import UploadFile, File
from services.annotation_service.database import get_db
from services.annotation_service.crud.feature_crud import FeatureCRUD
from services.annotation_service.crud.layer_crud import LayerCRUD
from services.annotation_service.crud.layer_field_crud import LayerFieldCRUD
from services.annotation_service.utils.shapefile_importer import parse_shapefile_bytes
from services.annotation_service.schemas.geojson import (
    FeatureCreate,
    FeatureUpdate,
    FeatureResponse,
    FeatureCollectionResponse
)

from services.annotation_service.schemas.layer_field import (
    LayerFieldCreate,
    LayerFieldUpdate,
    LayerFieldOut,
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


@router.delete("/layers/{layer_id}", tags=["CRUD"])
async def delete_layer(layer_id: UUID, db: AsyncSession = Depends(get_db)):
    crud = LayerCRUD(db)
    if not await crud.delete_layer(layer_id):
        raise HTTPException(status_code=404, detail="Layer not found")


@router.get(
    "/{layer_id}/fields",
    response_model=List[LayerFieldOut],
    summary="获取图层字段定义（属性表表头）"
)
async def list_fields(
    layer_id: UUID,
    db      : AsyncSession = Depends(get_db)
):
    """
    前端打开属性表时第一个调用的接口。
    返回该图层所有列的定义：名称、类型、顺序。
    """
    return await LayerFieldCRUD(db).get_by_layer(layer_id)


@router.post(
    "/{layer_id}/fields",
    response_model=LayerFieldOut,
    status_code=status.HTTP_201_CREATED,
    summary="新增字段（用户手动加列）"
)
async def create_field(
    layer_id: UUID,
    payload : LayerFieldCreate,
    db      : AsyncSession = Depends(get_db)
):
    try:
        return await LayerFieldCRUD(db).create(layer_id, payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch(
    "/{layer_id}/fields/{field_id}",
    response_model=LayerFieldOut,
    summary="修改字段定义（改别名、顺序等）"
)
async def update_field(
    layer_id: UUID,
    field_id: UUID,
    payload : LayerFieldUpdate,
    db      : AsyncSession = Depends(get_db)
):
    field = await LayerFieldCRUD(db).update(field_id, payload)
    if not field:
        raise HTTPException(status_code=404, detail="Field not found")
    return field


@router.delete(
    "/{layer_id}/fields/{field_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除字段（仅限用户自定义字段）"
)
async def delete_field(
    layer_id: UUID,
    field_id: UUID,
    db      : AsyncSession = Depends(get_db)
):
    try:
        deleted = await LayerFieldCRUD(db).delete(field_id)
        if not deleted:
            raise HTTPException(status_code=404, detail="Field not found")
    except PermissionError as e:
        raise HTTPException(status_code=403, detail=str(e))


@router.post(
    "/layers/{layer_id}/import/shapefile",
    status_code=status.HTTP_201_CREATED,
    tags=["Import"],
    summary="导入 Shapefile",
    description="上传 .shp/.shx/.dbf/.prj/.cpg 文件，批量导入矢量要素并自动注册字段定义。"
)
async def import_shapefile(
    layer_id: UUID,
    files: List[UploadFile] = File(..., description="同时上传 .shp/.shx/.dbf（必须）+ .prj/.cpg（推荐）"),
    db: AsyncSession = Depends(get_db)
):
    file_bytes: dict[str, bytes] = {}
    for f in files:
        content = await f.read()
        file_bytes[f.filename] = content
    try:
        feature_list, field_defs = parse_shapefile_bytes(file_bytes)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    if not feature_list:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Shapefile 中没有有效要素")
    field_crud = LayerFieldCRUD(db)
    existing_fields = await field_crud.get_by_layer(layer_id)
    existing_names = {f.field_name for f in existing_fields}

    for fd in field_defs:
        if fd["field_name"] not in existing_names:
            await field_crud.create(
                layer_id,
                LayerFieldCreate(
                    field_name=fd["field_name"],
                    field_alias=fd["field_alias"],
                    field_type=fd["field_type"],
                    is_system=False,
                )
            )
    feature_crud = FeatureCRUD(db)
    imported_count = await feature_crud.bulk_create(layer_id, feature_list)
    return {
        "imported": imported_count,
        "fields_registered": len(field_defs),
        "layer_id": str(layer_id),
    }
