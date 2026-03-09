import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

<<<<<<< HEAD
# 数据库连接字符串，与 data_service 保持一致
# 优先从环境变量读取，方便 Docker/K8s 部署
DATABASE_URL = os.getenv(
    "ANNOTATION_DATABASE_URL",
    "postgresql+asyncpg://rs_admin:rs_password@localhost:5432/vector_db"
)

# 创建异步引擎
# 增加了 pool_size 和 max_overflow 以应对 GIS 并发查询需求
=======
DATABASE_URL = os.getenv(
    "ANNOTATION_DATABASE_URL",
    "postgresql+asyncpg://rs_admin:rs_password@localhost:5432/rsmarking"
)

>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
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

<<<<<<< HEAD
# 声明基类
Base = declarative_base()


# 异步获取数据库会话的依赖项
async def get_db():
    """
    FastAPI 依赖注入项。
    增加了显式的回滚逻辑，确保空间事务的安全性。
    """
=======
Base = declarative_base()

async def get_db():
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
