import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# database connection string,text data_service text
# read from environment variables first,convenient for Docker/K8s deployment
DATABASE_URL = os.getenv(
    "ANNOTATION_DATABASE_URL",
    "postgresql+asyncpg://rs_admin:rs_password@localhost:5432/vector_db"
)

# create the async engine
# added pool_size text max_overflow to handle GIS concurrent query needs
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=20,          # base connection pool size
    max_overflow=10,       # allowed overflow connections
    pool_pre_ping=True     # automatically detect and recycle disconnected connections
)

# create the async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)

# declare base class
Base = declarative_base()


# dependency for obtaining an async database session
async def get_db():
    """
    FastAPI dependency injection item.
    addedexplicit rollback logic,ensure spatial transaction safety.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
