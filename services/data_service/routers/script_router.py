import logging

from fastapi import APIRouter, HTTPException, Depends, Form
from sqlalchemy.ext.asyncio import AsyncSession

from services.data_service.database import get_db
from services.data_service.bridges.executor_bridge import dispatch_user_script

logger = logging.getLogger("data_service.script")
router = APIRouter()

# 禁止在用户脚本中出现的危险关键字
DANGEROUS_KEYWORDS = [
    "__import__", "exec", "eval", "compile", "open(",
    "file(", "input(", "raw_input", "__builtins__",
    "globals(", "locals(",
]


@router.post("/execute-script")
async def execute_user_script(
        script: str = Form(...),
        raster_ids: str = Form(...),   # 逗号分隔的 ID 列表
        output_name: str = Form(...),
        db: AsyncSession = Depends(get_db)
):
    """执行用户自定义 Python 脚本"""
    try:
        ids = [int(id.strip()) for id in raster_ids.split(',') if id.strip()]
        script_lower = script.lower()

        for keyword in DANGEROUS_KEYWORDS:
            if keyword in script_lower:
                raise HTTPException(
                    status_code=400,
                    detail=f"脚本包含禁止的关键字: {keyword}"
                )

        result = await dispatch_user_script(db, script, ids, output_name)
        return {
            "status": "success",
            "message": "脚本执行完成",
            "result": result,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"脚本执行失败: {str(e)}")
        raise HTTPException(status_code=500, detail=f"脚本执行失败: {str(e)}")


@router.get("/script-templates")
async def get_script_templates():
    """获取预设的脚本模板"""
    return [
        {
            "name": "NDVI计算",
            "description": "使用红光和近红外波段计算NDVI",
            "code": (
                "import rasterio\nimport numpy as np\n\n"
                "with rasterio.open('/input/red.tif') as red_src:\n"
                "    red = red_src.read(1).astype(float)\n"
                "    profile = red_src.profile\n\n"
                "with rasterio.open('/input/nir.tif') as nir_src:\n"
                "    nir = nir_src.read(1).astype(float)\n\n"
                "ndvi = (nir - red) / (nir + red + 1e-8)\n"
                "ndvi = np.nan_to_num(ndvi, nan=-1)\n\n"
                "profile.update(dtype=rasterio.float32, count=1)\n"
                "with rasterio.open('/output/result.tif', 'w', **profile) as dst:\n"
                "    dst.write(ndvi.astype(np.float32), 1)\n\n"
                "print(f'NDVI calculation completed, range: [{ndvi.min():.3f}, {ndvi.max():.3f}]')"
            ),
        },
        {
            "name": "波段统计",
            "description": "计算影像的基本统计信息",
            "code": (
                "import rasterio\nimport numpy as np\n\n"
                "with rasterio.open('/input/image.tif') as src:\n"
                "    data = src.read()\n"
                "    print(f'Image shape: {data.shape}')\n"
                "    print(f'Number of bands: {src.count}')\n"
                "    print(f'Data type: {src.dtypes[0]}')\n"
                "    for i in range(src.count):\n"
                "        band = data[i]\n"
                "        print(f'\\nBand {i+1} statistics:')\n"
                "        print(f'  Min: {band.min():.3f}')\n"
                "        print(f'  Max: {band.max():.3f}')\n"
                "        print(f'  Mean: {band.mean():.3f}')\n"
                "        print(f'  Std: {band.std():.3f}')"
            ),
        },
        {
            "name": "自定义滤波",
            "description": "应用自定义卷积核进行空间滤波",
            "code": (
                "import rasterio\nimport numpy as np\nfrom scipy import ndimage\n\n"
                "with rasterio.open('/input/image.tif') as src:\n"
                "    data = src.read(1)\n"
                "    profile = src.profile\n\n"
                "filtered = ndimage.gaussian_filter(data, sigma=2)\n\n"
                "with rasterio.open('/output/result.tif', 'w', **profile) as dst:\n"
                "    dst.write(filtered.astype(profile['dtype']), 1)\n\n"
                "print('Filtering completed')"
            ),
        },
        {
            "name": "波段合成",
            "description": "多波段影像合成",
            "code": (
                "import rasterio\nimport numpy as np\n\n"
                "bands = []\nprofile = None\n\n"
                "for i in range(1, 4):\n"
                "    with rasterio.open(f'/input/band{i}.tif') as src:\n"
                "        bands.append(src.read(1))\n"
                "        if profile is None:\n"
                "            profile = src.profile\n\n"
                "composite = np.stack(bands)\n"
                "profile.update(count=len(bands))\n\n"
                "with rasterio.open('/output/composite.tif', 'w', **profile) as dst:\n"
                "    for i, band in enumerate(bands, 1):\n"
                "        dst.write(band, i)\n\n"
                "print(f'Created {len(bands)}-band composite image')"
            ),
        },
        {
            "name": "阈值分割",
            "description": "基于阈值的二值化分割",
            "code": (
                "import rasterio\nimport numpy as np\n"
                "from skimage.filters import threshold_otsu\n\n"
                "with rasterio.open('/input/image.tif') as src:\n"
                "    data = src.read(1)\n"
                "    profile = src.profile\n\n"
                "threshold = threshold_otsu(data)\n"
                "binary = (data > threshold).astype(np.uint8) * 255\n\n"
                "profile.update(dtype=rasterio.uint8, count=1)\n\n"
                "with rasterio.open('/output/binary.tif', 'w', **profile) as dst:\n"
                "    dst.write(binary, 1)\n\n"
                "print(f'Threshold segmentation completed (threshold={threshold:.2f})')"
            ),
        },
    ]
