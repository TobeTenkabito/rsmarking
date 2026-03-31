import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import text

from services.annotation_service.database import engine
from services.annotation_service.router import layers_router, projects_router, spatial_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as e:
        print(f"Critical Error: Database connection failed: {e}")
        raise e
    yield
    await engine.dispose()

app = FastAPI(
    title="Annotation Service",
    description="Microservice for RS remote sensing vector data management",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(layers_router.router)
app.include_router(projects_router.router)
app.include_router(spatial_router.router)

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
