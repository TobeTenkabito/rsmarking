import uvicorn
from fastapi import FastAPI, Depends, HTTPException, Path, Query
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy import text
from typing import Optional
from uuid import UUID
import os

# =============================================================================
# DATABASE CONFIGURATION (Optimized for Read)
# =============================================================================

DATABASE_URL = os.getenv(
    "VTILER_DATABASE_URL",
    "postgresql+asyncpg://rs_admin:rs_password@localhost:5432/vector_db"
)

# 使用专用的只读引擎，增大连接池以支持瓦片并发拉取
engine = create_async_engine(
    DATABASE_URL,
    pool_size=40,
    max_overflow=20,
    pool_pre_ping=True
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False
)


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


# =============================================================================
# FASTAPI APP
# =============================================================================

app = FastAPI(
    title="Vector Tile Service",
    description="High-performance MVT rendering engine using PostGIS"
)


# =============================================================================
# CORE RENDERING LOGIC (ST_AsMVT Implementation)
# =============================================================================

@app.get(
    "/tiles/{layer_id}/{z}/{x}/{y}.pbf",
    summary="Get Vector Tile",
    description="Returns a Mapbox Vector Tile (MVT) generated directly from PostGIS"
)
async def get_tile(
        layer_id: UUID = Path(..., description="The ID of the annotation layer"),
        z: int = Path(..., ge=0, le=24),
        x: int = Path(...),
        y: int = Path(...),
        db: AsyncSession = Depends(get_db)
):
    """
    1. Calculate BBox of the tile in Web Mercator (EPSG:3857).
    2. Convert BBox to EPSG:4326 for spatial index query.
    3. Use ST_AsMVT to encode geometry into PBF format.
    """

    # SQL query using PostGIS ST_AsMVT for maximum performance
    # ST_AsMVTGeom converts geometries to tile coordinates (0-4096)
    # ST_TileEnvelope generates the tile's bounding box
    mvt_query = text("""
        WITH 
        bounds AS (
          SELECT ST_TileEnvelope(:z, :x, :y) AS geom_3857
        ),
        mvt_geom AS (
          SELECT 
            id,
            category,
            properties,
            ST_AsMVTGeom(
                ST_Transform(geom, 3857), 
                bounds.geom_3857, 
                4096, 
                64, 
                true
            ) AS geom
          FROM features, bounds
          WHERE layer_id = :layer_id
          AND ST_Intersects(geom, ST_Transform(bounds.geom_3857, 4326))
        )
        SELECT ST_AsMVT(mvt_geom.*, 'default') FROM mvt_geom;
    """)

    try:
        result = await db.execute(mvt_query, {"z": z, "x": x, "y": y, "layer_id": layer_id})
        tile_content = result.scalar()

        if not tile_content:
            # Return empty 204 if no data in this tile area
            return Response(status_code=204)

        return Response(
            content=bytes(tile_content),
            media_type="application/x-protobuf",
            headers={
                "Content-Disposition": f"attachment; filename={y}.pbf",
                "Cache-Control": "public, max-age=3600"  # Cache tiles for 1 hour
            }
        )
    except Exception as e:
        # Standard error response for tile generation failures
        raise HTTPException(status_code=500, detail=f"Tile rendering error: {str(e)}")


from fastapi import Response


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.get("/health")
async def health_check():
    return {"status": "running", "engine": "PostGIS ST_AsMVT"}


if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8003, reload=True)