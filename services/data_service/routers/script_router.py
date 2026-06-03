import logging

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.bridges.executor_bridge import dispatch_user_script
from services.data_service.database import get_db
from services.executor_service.security import validate_script_content

logger = logging.getLogger("data_service.script")
router = APIRouter()


@router.post("/execute-script")
async def execute_user_script(
    script: str = Form(...),
    raster_ids: str = Form(...),
    output_name: str = Form(...),
    db: AsyncSession = Depends(get_db),
):
    try:
        ids = [int(item.strip()) for item in raster_ids.split(",") if item.strip()]
        if not ids:
            raise HTTPException(status_code=400, detail="At least one raster ID is required")

        is_valid, blocked_label = validate_script_content(script)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Script contains a blocked operation: {blocked_label}",
            )

        result = await dispatch_user_script(db, script, ids, output_name)
        return {
            "status": "success",
            "message": "Script execution completed",
            "result": result,
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Script execution failed: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"Script execution failed: {e}")


@router.get("/script-templates")
async def get_script_templates():
    return [
        {
            "name": "NDVI Calculation",
            "description": "Use the first two input rasters as red and NIR bands to compute NDVI.",
            "code": (
                "import rasterio\n"
                "import numpy as np\n\n"
                "red_path = input_0\n"
                "nir_path = input_1\n\n"
                "with rasterio.open(red_path) as red_src:\n"
                "    red = red_src.read(1).astype(np.float32)\n"
                "    profile = red_src.profile\n\n"
                "with rasterio.open(nir_path) as nir_src:\n"
                "    nir = nir_src.read(1).astype(np.float32)\n\n"
                "ndvi = (nir - red) / (nir + red + 1e-8)\n"
                "ndvi = np.nan_to_num(ndvi, nan=-1.0)\n\n"
                "profile.update(dtype=rasterio.float32, count=1)\n"
                "with rasterio.open(OUTPUT_FILE, 'w', **profile) as dst:\n"
                "    dst.write(ndvi.astype(np.float32), 1)\n\n"
                "print(f'NDVI complete, range: [{ndvi.min():.3f}, {ndvi.max():.3f}]')\n"
            ),
        },
        {
            "name": "Band Statistics",
            "description": "Print basic statistics for the first input raster.",
            "code": (
                "import rasterio\n"
                "import numpy as np\n\n"
                "with rasterio.open(input_0) as src:\n"
                "    data = src.read()\n"
                "    print(f'Image shape: {data.shape}')\n"
                "    print(f'Band count: {src.count}')\n"
                "    print(f'Data type: {src.dtypes[0]}')\n"
                "    for i in range(src.count):\n"
                "        band = data[i]\n"
                "        print(f'Band {i + 1}: min={band.min():.3f}, max={band.max():.3f}, mean={band.mean():.3f}, std={band.std():.3f}')\n"
            ),
        },
        {
            "name": "Gaussian Filter",
            "description": "Apply a Gaussian filter to the first input raster.",
            "code": (
                "import rasterio\n"
                "from scipy import ndimage\n\n"
                "with rasterio.open(input_0) as src:\n"
                "    data = src.read(1)\n"
                "    profile = src.profile\n\n"
                "filtered = ndimage.gaussian_filter(data, sigma=2)\n\n"
                "with rasterio.open(OUTPUT_FILE, 'w', **profile) as dst:\n"
                "    dst.write(filtered.astype(profile['dtype']), 1)\n\n"
                "print('Filtering completed')\n"
            ),
        },
        {
            "name": "Band Composite",
            "description": "Stack the first three input rasters into a multi-band composite.",
            "code": (
                "import rasterio\n"
                "import numpy as np\n\n"
                "bands = []\n"
                "profile = None\n\n"
                "for path in (input_0, input_1, input_2):\n"
                "    with rasterio.open(path) as src:\n"
                "        bands.append(src.read(1))\n"
                "        if profile is None:\n"
                "            profile = src.profile\n\n"
                "profile.update(count=len(bands))\n"
                "with rasterio.open(OUTPUT_FILE, 'w', **profile) as dst:\n"
                "    for i, band in enumerate(bands, start=1):\n"
                "        dst.write(band, i)\n\n"
                "print(f'Created {len(bands)}-band composite image')\n"
            ),
        },
        {
            "name": "Otsu Threshold",
            "description": "Apply Otsu thresholding to the first input raster.",
            "code": (
                "import rasterio\n"
                "import numpy as np\n"
                "from skimage.filters import threshold_otsu\n\n"
                "with rasterio.open(input_0) as src:\n"
                "    data = src.read(1)\n"
                "    profile = src.profile\n\n"
                "threshold = threshold_otsu(data)\n"
                "binary = (data > threshold).astype(np.uint8) * 255\n"
                "profile.update(dtype=rasterio.uint8, count=1)\n\n"
                "with rasterio.open(OUTPUT_FILE, 'w', **profile) as dst:\n"
                "    dst.write(binary, 1)\n\n"
                "print(f'Otsu threshold complete (threshold={threshold:.4f})')\n"
            ),
        },
    ]
