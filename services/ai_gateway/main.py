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

from services.ai_gateway.router import router as ai_router

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s"
)
logger = logging.getLogger("ai_gateway.service")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("=== AI GATEWAY SERVICE STARTUP BEGIN ===")
    logger.info("=== AI GATEWAY SERVICE STARTUP OK ===")
    yield
    logger.info("=== AI GATEWAY SERVICE SHUTDOWN ===")


app = FastAPI(
    title="AI Gateway Service",
    description="智能空间数据网关 - 独立服务",
    version="1.0.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(ai_router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8006, reload=True)
