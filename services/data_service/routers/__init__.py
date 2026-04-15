from fastapi import APIRouter

from services.data_service.routers.upload_router import router as upload_router
from services.data_service.routers.indices_router import router as indices_router
from services.data_service.routers.extract_router import router as extract_router
from services.data_service.routers.clip_router import router as clip_router
from services.data_service.routers.raster_router import router as raster_router
from services.data_service.routers.field_router import router as field_router
from services.data_service.routers.script_router import router as script_router
from services.data_service.routers.change_router import router as change_router
from services.data_service.routers.rasterize_router import router as rasterize_router

router = APIRouter()

router.include_router(upload_router)
router.include_router(indices_router)
router.include_router(extract_router)
router.include_router(clip_router)
router.include_router(raster_router)
router.include_router(field_router)
router.include_router(script_router)
router.include_router(change_router)
router.include_router(rasterize_router)
