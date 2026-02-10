import io
import os
import logging
import numpy as np
import rasterio
import mercantile
import traceback
from fastapi import FastAPI, HTTPException, Response, Depends
from fastapi.middleware.cors import CORSMiddleware
from PIL import Image
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from rasterio.windows import from_bounds, Window
from rasterio.enums import Resampling
from rasterio.warp import transform_bounds

try:
    from services.tile_service.core.config import settings
    from services.tile_service.core.cache import tile_cache
    from services.tile_service.engine.tiler import TileEngine
    from services.data_service.database import engine, AsyncSessionLocal, get_db
except ImportError as e:
    print(f"### [CRITICAL] 模块导入失败: {e} ###")
    from core.config import settings
    from core.cache import tile_cache
    from engine.tiler import TileEngine
    from services.data_service.database import engine, AsyncSessionLocal, get_db

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tile_service")

app = FastAPI(title=settings.PROJECT_NAME)

print("\n" + "=" * 50)
print("### [SERVER] TILE SERVICE IS STARTING... ###")
print(f"### [SERVER] PORT: 8005 ###")
print("=" * 50 + "\n")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


async def get_raster_path(db: AsyncSession, index_id: str) -> str:
    print(f"[DB_QUERY] 正在查找标识符: {index_id} (类型: {type(index_id)})")
    try:
        try:
            val = int(index_id)
            print(f"[DB_QUERY] 标识符识别为整数: {val}")
        except ValueError:
            val = index_id
            print(f"[DB_QUERY] 标识符识别为字符串: {val}")

        query = text("SELECT file_path FROM raster_metadata WHERE index_id = :val OR id = :val")
        result = await db.execute(query, {"val": val})
        row = result.one_or_none()

        if row:
            print(f"[DB_QUERY] ✅ 查找到路径: {row[0]}")
            return row[0]
        else:
            print(f"[DB_QUERY] ❌ 未查找到任何匹配记录")
            return None
    except Exception as e:
        print(f"[DB_QUERY] 💥 数据库查询崩溃: {str(e)}")
        logger.error(f"Database error for identifier {index_id}: {e}")
        return None


def process_tile_pixels_internal(data):
    count, height, width = data.shape
    print(f"[PROCESS] 处理像素数据块: Shape={data.shape}, dtype={data.dtype}")

    processed = []
    for i in range(count):
        band = data[i].astype(np.float32)
        b_min = np.percentile(band, 2)
        b_max = np.percentile(band, 98)
        print(f"[PROCESS] 波段 {i}: min={band.min()}, max={band.max()}, 2%={b_min}, 98%={b_max}")

        if b_max > b_min:
            stretched = (band - b_min) / (b_max - b_min) * 255
            processed.append(np.clip(stretched, 0, 255).astype(np.uint8))
        else:
            processed.append(np.zeros((height, width), dtype=np.uint8))

    if count >= 3:
        rgb = np.stack([processed[0], processed[1], processed[2]], axis=-1)
    elif count > 0:
        rgb = np.stack([processed[0]] * 3, axis=-1)
    else:
        rgb = np.zeros((height, width, 3), dtype=np.uint8)

    alpha = np.where(np.max(data, axis=0) > 0, 255, 0).astype(np.uint8)
    return np.dstack([rgb, alpha])


@app.get("/tile/{index_id}/{z}/{x}/{y}.png")
async def get_tile(
        index_id: str, z: int, x: int, y: int,
        bands: str = settings.DEFAULT_BANDS,
        db: AsyncSession = Depends(get_db)
):
    file_path = await get_raster_path(db, index_id)
    if not file_path or not os.path.exists(file_path):
        img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return Response(content=buf.getvalue(), media_type="image/png")

    try:
        global_stats = {"low": [0, 0, 0], "high": [6000, 6000, 6000]}
        engine = TileEngine(file_path)
        requested_bands = [int(b) for b in bands.split(",")]

        tile_data = engine.read_tile(x, y, z, bands=requested_bands, stats=global_stats)

        if tile_data is None:
            img = Image.new('RGBA', (256, 256), (0, 0, 0, 0))
        else:
            img = Image.fromarray(tile_data)

        buf = io.BytesIO()
        img.save(buf, format='PNG')
        return Response(content=buf.getvalue(), media_type="image/png")

    except Exception as e:
        print(f"[TILE_SERVICE_ERROR] {e}")
        traceback.print_exc()
        return Response(status_code=500)


@app.get("/debug/render-first.png")
async def debug_render_first(db: AsyncSession = Depends(get_db)):
    print("\n[DEBUG] >>> 运行 RENDER-FIRST 验证流程...")
    query = text("SELECT index_id, file_path FROM raster_metadata ORDER BY id DESC LIMIT 1")
    result = await db.execute(query)
    row = result.fetchone()

    if not row:
        print("[DEBUG] ❌ 数据库空空如也")
        raise HTTPException(status_code=404, detail="No raster records found")

    index_id, file_path = row
    print(f"[DEBUG] 测试目标: ID={index_id}, Path={file_path}")

    try:
        z, x, y = 2, 2, 1
        with rasterio.open(file_path) as src:
            print(f"[DEBUG] 文件打开成功: CRS={src.crs}, Transform={src.transform}")
            tile_bounds = mercantile.xy_bounds(x, y, z)
            print(f"[DEBUG] 瓦片地理范围 (WebMercator): {tile_bounds}")
            window = from_bounds(tile_bounds.left, tile_bounds.bottom, tile_bounds.right, tile_bounds.top,
                                 src.transform)
            print(f"[DEBUG] 对应像素 Window: {window}")

            band_indices = list(range(1, min(3, src.count) + 1))
            tile_data = src.read(
                band_indices,
                window=window,
                out_shape=(len(band_indices), 256, 256),
                resampling=Resampling.bilinear,
                boundless=True,
                fill_value=0
            )

            img_rgba = process_tile_pixels_internal(tile_data)
            img = Image.fromarray(img_rgba)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            print("[DEBUG] ✅ RENDER-FIRST 生成完毕")
            return Response(content=buf.getvalue(), media_type="image/png")

    except Exception as e:
        print(f"[DEBUG] ❌ RENDER-FIRST 失败: {str(e)}")
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/debug/fast_check.png")
async def debug_fast_check(db: AsyncSession = Depends(get_db)):
    print("\n[DEBUG] >>> 运行 FAST_CHECK 验证流程...")
    query = text("SELECT index_id, file_path FROM raster_metadata ORDER BY id DESC LIMIT 1")
    result = await db.execute(query)
    row = result.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="No records")

    index_id, file_path = row
    try:
        with rasterio.open(file_path) as src:
            center_x, center_y = src.width // 2, src.height // 2
            window = Window(center_x - 128, center_y - 128, 256, 256)
            bands_to_read = min(3, src.count)
            tile_data = src.read(list(range(1, bands_to_read + 1)), window=window, out_shape=(bands_to_read, 256, 256),
                                 resampling=Resampling.bilinear, boundless=True, fill_value=0)

            img_rgba = process_tile_pixels_internal(tile_data)
            img = Image.fromarray(img_rgba)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return Response(content=buf.getvalue(), media_type="image/png")
    except Exception as e:
        print(f"[DEBUG] ❌ FAST_CHECK 失败: {str(e)}")
        traceback.print_exc()
        return Response(status_code=500)


@app.get("/health")
async def health():
    return {"status": "ready", "engine": "cython-accelerated", "logs": "verbose_mode"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8005)
