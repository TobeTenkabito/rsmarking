import sys
import os
import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
BASE_DIR = os.path.abspath(os.path.join(CURRENT_DIR, "..", ".."))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from services.tile_service.core.config import settings
from services.tile_service.control import router as tile_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("tile_service_init")

app = FastAPI(
    title=f"{settings.PROJECT_NAME} - Tile Service",
    description="High-performance map tile server with Cython acceleration.",
    version="2.0.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(tile_router)

@app.get("/health")
async def health():
    return {
        "status": "ready",
        "service": "tile_service",
        "engine": "cython-accelerated"
    }

if __name__ == "__main__":
    import uvicorn
    print("\n" + "=" * 50)
    print(f"### [SERVER] TILE SERVICE IS STARTING ON PORT 8005 ###")
    print("=" * 50 + "\n")
    uvicorn.run("main:app", host="0.0.0.0", port=8005, reload=True)
