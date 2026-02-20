import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

DATABASE_URL = os.getenv(
    "ANNOTATION_DATABASE_URL",
    "postgresql+asyncpg://rs_admin:rs_password@localhost:5432/rsmarking"
)

engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,          # 基础连接池大小
    max_overflow=10,       # 允许超出的连接数
    pool_pre_ping=True     # 自动检测并回收断开的连接
)

# 创建异步会话工厂
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

Base = declarative_base()

async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def init_db():
    from .models.feature import Base as FeatureBase
    async with engine.begin() as conn:
        await conn.run_sync(FeatureBase.metadata.create_all)
