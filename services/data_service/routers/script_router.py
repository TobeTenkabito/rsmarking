import logging
from uuid import UUID

from fastapi import APIRouter, Depends, Form, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.bridges.executor_bridge import (
    _sandbox_feature_alias,
    dispatch_user_script,
)
from services.data_service.bridges.vector_bridge import internal_fetch_feature
from services.data_service.database import get_db
from services.executor_service.security import validate_script_content

logger = logging.getLogger("data_service.script")
router = APIRouter()


@router.post("/execute-script")
async def execute_user_script(
    script: str = Form(...),
    raster_ids: str = Form(""),
    feature_ids: str = Form(""),
    output_name: str = Form(...),
    output_required: bool = Form(False),
    db: AsyncSession = Depends(get_db),
):
    try:
        try:
            ids = [int(item.strip()) for item in raster_ids.split(",") if item.strip()]
        except ValueError:
            raise HTTPException(status_code=400, detail="raster_ids must contain integers")

        try:
            vector_ids = [
                UUID(item.strip())
                for item in feature_ids.split(",")
                if item.strip()
            ]
        except ValueError:
            raise HTTPException(status_code=400, detail="feature_ids must contain UUID values")

        if not ids and not vector_ids:
            raise HTTPException(
                status_code=400,
                detail="Select at least one raster or vector feature for the sandbox",
            )

        is_valid, blocked_label = validate_script_content(script)
        if not is_valid:
            raise HTTPException(
                status_code=400,
                detail=f"Script contains a blocked operation: {blocked_label}",
            )

        vector_inputs = []
        for feature_id in dict.fromkeys(vector_ids):
            feature = await internal_fetch_feature(feature_id)
            layer_id = feature.get("layer_id")
            vector_inputs.append(
                {
                    "name": f"feature_{feature_id}.geojson",
                    "alias": _sandbox_feature_alias(str(feature_id)),
                    "feature_id": str(feature_id),
                    "layer_id": str(layer_id) if layer_id is not None else None,
                    "geojson": feature,
                }
            )

        result = await dispatch_user_script(
            db,
            script,
            ids,
            output_name,
            vector_inputs=vector_inputs,
            output_required=output_required,
        )
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
                "    red = red_src.read(1, masked=True).astype(np.float32)\n"
                "    profile = red_src.profile\n\n"
                "with rasterio.open(nir_path) as nir_src:\n"
                "    nir = nir_src.read(1, masked=True).astype(np.float32)\n\n"
                "ndvi = (nir - red) / (nir + red + 1e-8)\n"
                "ndvi = np.ma.masked_invalid(ndvi.astype(np.float32))\n\n"
                "profile.update(dtype=rasterio.float32, count=1, nodata=-9999.0)\n"
                "write_raster(ndvi, profile)\n\n"
                "valid = ndvi.compressed()\n"
                "print(f'NDVI complete, valid pixels: {valid.size}, range: [{valid.min():.3f}, {valid.max():.3f}]')\n"
            ),
        },
        {
            "name": "Band Statistics",
            "description": "Print basic statistics for the first input raster.",
            "code": (
                "import rasterio\n"
                "import numpy as np\n\n"
                "with rasterio.open(input_0) as src:\n"
                "    data = src.read(masked=True)\n"
                "    if src.nodata is None and not np.any(np.ma.getmaskarray(data)):\n"
                "        data = np.ma.masked_equal(data, 0)\n"
                "    print(f'Image shape: {data.shape}')\n"
                "    print(f'Band count: {src.count}')\n"
                "    print(f'Data type: {src.dtypes[0]}')\n"
                "    for i in range(src.count):\n"
                "        band = data[i].compressed()\n"
                "        if band.size:\n"
                "            print(f'Band {i + 1}: valid={band.size}, min={band.min():.3f}, max={band.max():.3f}, mean={band.mean():.3f}, std={band.std():.3f}')\n"
            ),
        },
        {
            "name": "Gaussian Filter",
            "description": "Apply a Gaussian filter to the first input raster.",
            "code": (
                "import rasterio\n"
                "import numpy as np\n"
                "from scipy import ndimage\n\n"
                "with rasterio.open(input_0) as src:\n"
                "    data = src.read(1, masked=True)\n"
                "    profile = src.profile\n\n"
                "filtered = ndimage.gaussian_filter(data.filled(0), sigma=2)\n"
                "filtered = np.ma.array(filtered, mask=np.ma.getmaskarray(data))\n\n"
                "write_raster(filtered.astype(profile['dtype']), profile)\n\n"
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
                "        bands.append(src.read(1, masked=True))\n"
                "        if profile is None:\n"
                "            profile = src.profile\n\n"
                "composite = np.ma.stack(bands)\n"
                "profile.update(count=len(bands))\n"
                "write_raster(composite, profile)\n\n"
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
                "    data = src.read(1, masked=True)\n"
                "    profile = src.profile\n\n"
                "threshold = threshold_otsu(data.compressed())\n"
                "binary = np.ma.array((data.filled(0) > threshold).astype(np.uint8) * 255,\n"
                "                     mask=np.ma.getmaskarray(data))\n"
                "profile.update(dtype=rasterio.uint8, count=1, nodata=0)\n\n"
                "write_raster(binary, profile)\n\n"
                "print(f'Otsu threshold complete (threshold={threshold:.4f})')\n"
            ),
        },
    ]
