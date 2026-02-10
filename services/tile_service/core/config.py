import os
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "RSMarking-TileService"
    STORAGE_RAW_DIR: str = os.getenv("STORAGE_RAW_DIR", "/app/storage/raw")
    CACHE_L1_SIZE: int = 1024
    CACHE_L2_DIR: str = os.path.join(os.path.dirname(__file__), "../../.tile_cache")
    CACHE_L2_SIZE_LIMIT: int = 5 * 1024 * 1024 * 1024
    DEFAULT_BANDS: str = "1,2,3"
    TILE_SIZE: int = 256
    class Config:
        env_file = ".env"

settings = Settings()
