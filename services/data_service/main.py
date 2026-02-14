import sys
import os
import logging
from contextlib import asynccontextmanager

CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))

if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text


from services.data_service.database import engine, Base
from services.data_service.control import router as data_router


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("data_service_init")

UPLOAD_DIR = os.path.join(BASE_DIR, "storage", "raw")
COG_DIR = os.path.join(BASE_DIR, "storage", "cog")
CLIENT_DIR = os.path.join(BASE_DIR, "client")

os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(COG_DIR, exist_ok=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== DATA SERVICE STARTUP BEGIN ===")
    logger.info(f"[DB] engine.url = {engine.url}")
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT current_database()"))
            db_name = result.scalar()
            result = await conn.execute(text("SELECT current_schema()"))
            schema = result.scalar()
            logger.info(f"[DB] database = {db_name}, schema = {schema}")
            logger.info(f"[DB] Base.metadata.tables = {list(Base.metadata.tables.keys())}")
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        async with engine.connect() as conn:
            result = await conn.execute(text("""
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
            """))
            tables = [r[0] for r in result.fetchall()]
            logger.info(f"[DB] tables in public schema: {tables}")

        logger.info("=== DATA SERVICE STARTUP OK ===")
    except Exception as e:
        logger.error(f"=== DATA SERVICE STARTUP FAILED: {str(e)} ===")
        raise e
    yield

app = FastAPI(
    title="Raster Processing Service",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

if os.path.exists(COG_DIR):
    app.mount("/data", StaticFiles(directory=os.path.abspath(COG_DIR)), name="cog_data")
    logger.info(f"已挂载 COG 数据路径: {COG_DIR}")
else:
    logger.warning(f"COG 目录不存在: {COG_DIR}")

if os.path.exists(CLIENT_DIR):
    app.mount("/client", StaticFiles(directory=CLIENT_DIR), name="client")
    logger.info(f"已成功挂载 /client 路径: {CLIENT_DIR}")
else:
    logger.warning(f"Client 目录不存在: {CLIENT_DIR}")


app.include_router(data_router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8002, reload=True)
