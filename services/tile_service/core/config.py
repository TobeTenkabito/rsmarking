import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "RSMarking-TileService"
    STORAGE_RAW_DIR: str = os.getenv("STORAGE_RAW_DIR", "/app/storage/raw")
    CACHE_L1_SIZE: int = 1024
    CACHE_L2_DIR: str = os.path.join(os.path.dirname(__file__), "../../.tile_cache")
    CACHE_L2_SIZE_LIMIT: int = 5 * 1024 * 1024 * 1024
    DEFAULT_BANDS: str = "1,2,3"
    TILE_SIZE: int = 256
    TILE_PROFILE: bool = False
    TILE_ALPHA_MODE: str = "auto"
    TILE_PATH_CACHE_TTL_SECONDS: float = 30.0
    TILE_PATH_CACHE_MAXSIZE: int = 1024
    TILE_RASTER_OPEN_MODE: str = "per_request"
    TILE_RESAMPLING_MODE: str = "quality"
    TILE_PNG_COMPRESS_LEVEL: int = 1


settings = Settings()
