import logging
from typing import Literal

from fastapi import APIRouter, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

import services.data_service.db_ops as db_ops
from services.data_service.database import get_db


logger = logging.getLogger("data_service.transform")
router = APIRouter()


@router.post("/raster-transform-analysis")
async def raster_transform_analysis(
    raster_id: int = Form(...),
    transform_type: Literal["fourier", "wavelet", "pca"] = Form(...),
    new_name: str = Form(...),
    band_index: int = Form(1),
    fourier_output: Literal["magnitude", "power", "phase"] = Form("magnitude"),
    wavelet_output: Literal["detail_energy", "approximation", "horizontal", "vertical", "diagonal"] = Form("detail_energy"),
    wavelet_level: int = Form(1),
    pca_components: int = Form(3),
    pca_standardize: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    return await db_ops.process_raster_transform_task(
        db=db,
        raster_id=raster_id,
        transform_type=transform_type,
        new_name=new_name,
        band_index=band_index,
        fourier_output=fourier_output,
        wavelet_output=wavelet_output,
        wavelet_level=wavelet_level,
        pca_components=pca_components,
        pca_standardize=pca_standardize,
    )
