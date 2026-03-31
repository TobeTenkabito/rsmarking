"""
router.py —— 顶层路由聚合入口
"""
from fastapi import APIRouter
from services.data_service.routers import router as sub_router

router = APIRouter()
router.include_router(sub_router)
