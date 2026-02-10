from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# 数据库连接字符串 (请根据你的 PostGIS 配置修改)
# 格式: postgresql+asyncpg://用户名:密码@地址:端口/数据库名
DATABASE_URL = "postgresql+asyncpg://rs_admin:rs_password@localhost:5432/rsmarking"

# 创建异步引擎
engine = create_async_engine(DATABASE_URL, echo=False)

# 创建异步会话工厂
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


# 异步获取数据库会话的依赖项
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
