"""
router.py - text
"""
from fastapi import APIRouter
from services.data_service.routers import router as sub_router

router = APIRouter()
router.include_router(sub_router)
