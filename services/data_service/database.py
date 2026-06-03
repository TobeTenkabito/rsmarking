from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.declarative import declarative_base

# database connection string (by PostGIS text)
# format: postgresql+asyncpg://username:password@address:port/database name
DATABASE_URL = "postgresql+asyncpg://rs_admin:rs_password@localhost:5432/rsmarking"

# create the async engine
engine = create_async_engine(DATABASE_URL, echo=False)

# create the async session factory
AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

Base = declarative_base()


# dependency for obtaining an async database session
async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
