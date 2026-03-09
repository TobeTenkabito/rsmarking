import os
import logging
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv

# 获取路径
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(CURRENT_DIR, "../../"))

# 加载环境变量
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# 数据库配置 - 注意：Tile服务通常使用同步连接以配合地理计算库
DATABASE_URL = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")  # 强制转为同步驱动

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tile_service")

app = FastAPI()

# 数据库初始化
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def check_db_content():
    """核心排查：检查数据库里到底有没有数据"""
    try:
        with engine.connect() as conn:
            # 替换为你的实际表名，查看记录总数
            result = conn.execute(text("SELECT COUNT(*) FROM marks"))
            count = result.scalar()
            logger.info(f"📊 数据库自检：marks 表中有 {count} 条数据")
            return count
    except Exception as e:
        logger.error(f"❌ 数据库自检失败：{str(e)}")
        return 0


@app.on_event("startup")
async def startup_event():
    logger.info(f"🚀 Tile Service 启动")
    logger.info(f"根目录: {PROJECT_ROOT}")
    check_db_content()


@app.get("/tile/{index_id}/{z}/{x}/{y}")
async def get_tile(index_id: str, z: int, x: int, y: int):
    # 路径排查逻辑
    # 假设你的瓦片存储在一级目录的 data/tiles 下
    tile_dir = os.path.join(PROJECT_ROOT, "data", "tiles", index_id)

    logger.info(f"正在查找 index_id: {index_id}, 预期目录: {tile_dir}")

    if not os.path.exists(tile_dir):
        # 如果目录不存在，列出父目录内容帮助调试
        parent_dir = os.path.dirname(tile_dir)
        exists_dirs = os.listdir(parent_dir) if os.path.exists(parent_dir) else "Parent not found"
        logger.error(f"找不到文件。当前父目录下存在: {exists_dirs}")
        raise HTTPException(status_code=404, detail=f"Index ID {index_id} folder not found")

    # 这里继续你的切片逻辑...
    return {"message": "Folder found", "path": tile_dir}


@app.get("/debug/db")
async def debug_db():
    """手动触发数据库检查"""
    count = check_db_content()
    return {"count": count, "url": DATABASE_URL.split('@')[-1]}