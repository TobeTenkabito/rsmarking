import os
import logging
import asyncio
from pathlib import Path
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete, text
from typing import List, Optional
from services.data_service.models import RasterMetadata

logger = logging.getLogger("data_service.crud")
STORAGE_DIR = Path(__file__).resolve().parents[3] / "storage"


class RasterCRUD:

    @staticmethod
    async def create_raster(db: AsyncSession, metadata_dict: dict):
        """save imagery metadata"""
        cog_url = metadata_dict.get("cog_path") or metadata_dict.get("cog_url")
        res_x = metadata_dict.get("resolution_x")
        res_y = metadata_dict.get("resolution_y")

        if "resolution" in metadata_dict and (res_x is None or res_y is None):
            res = metadata_dict["resolution"]
            if res:
                res_x, res_y = res[0], res[1]

        db_obj = RasterMetadata(
            file_name=metadata_dict.get("file_name"),
            bundle_id=metadata_dict.get("bundle_id"),
            index_id=metadata_dict.get("index_id"),
            file_path=metadata_dict.get("file_path"),
            cog_path=cog_url,
            crs=metadata_dict.get("crs"),
            bounds=metadata_dict.get("bounds"),
            bounds_wgs84=metadata_dict.get("bounds_wgs84"),
            center=metadata_dict.get("center"),
            width=metadata_dict.get("width"),
            height=metadata_dict.get("height"),
            bands=metadata_dict.get("bands"),
            data_type=metadata_dict.get("data_type"),
            resolution_x=res_x,
            resolution_y=res_y,
            acquired_at=metadata_dict.get("acquired_at"),
            acquired_at_end=metadata_dict.get("acquired_at_end"),
            acquired_at_source=metadata_dict.get("acquired_at_source") or "unknown",
            acquired_at_confidence=metadata_dict.get("acquired_at_confidence") or 0.0,
            platform=metadata_dict.get("platform"),
            sensor=metadata_dict.get("sensor"),
            product_id=metadata_dict.get("product_id"),
            processing_level=metadata_dict.get("processing_level"),
            tile_id=metadata_dict.get("tile_id"),
        )
        db.add(db_obj)
        await db.flush()
        return db_obj

    @staticmethod
    async def get_all_rasters(db: AsyncSession) -> List[RasterMetadata]:
        """get all imagery"""
        stmt = select(RasterMetadata).order_by(RasterMetadata.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_raster_by_index_id(db: AsyncSession, raster_id: int) -> Optional[RasterMetadata]:
        """bydatabaseIDimageryrecord"""
        stmt = select(RasterMetadata).where(RasterMetadata.index_id == raster_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_rasters_by_bundle(db: AsyncSession, bundle_id: str) -> List[RasterMetadata]:
        """bybundle_idquery"""
        stmt = select(RasterMetadata).where(RasterMetadata.bundle_id == bundle_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def delete_raster(db: AsyncSession, raster_id: int) -> bool:
        """delete a single imagery item"""
        await RasterCRUD.lock_raster_writes(db)
        stmt = select(RasterMetadata).where(RasterMetadata.id == raster_id)
        result = await db.execute(stmt)
        raster = result.scalar_one_or_none()
        if not raster:
            await db.rollback()
            return False
        paths = RasterCRUD._physical_paths(raster.file_path, raster.cog_path)
        await db.delete(raster)
        await db.commit()
        await RasterCRUD._cleanup_unreferenced_files(db, paths)
        return True

    @staticmethod
    async def clear_all_rasters(db: AsyncSession) -> bool:
        """clear the database and delete all files"""
        await RasterCRUD.lock_raster_writes(db)
        stmt = select(RasterMetadata.file_path, RasterMetadata.cog_path)
        result = await db.execute(stmt)
        rows = result.all()
        paths = set()
        for file_path, cog_path in rows:
            paths.update(RasterCRUD._physical_paths(file_path, cog_path))
        await db.execute(delete(RasterMetadata))
        await db.commit()
        await RasterCRUD._cleanup_unreferenced_files(db, paths)
        logger.info("Raster metadata cleared; unreferenced managed files cleaned up.")
        return True

    @staticmethod
    async def lock_raster_writes(db: AsyncSession):
        """Serialize deletion/cleanup and shared-file copies with all table writes.

        PostgreSQL inserts and updates acquire ROW EXCLUSIVE locks, which conflict
        with this lock. It is released when the caller commits or rolls back.
        """
        await db.execute(text("LOCK TABLE raster_metadata IN SHARE ROW EXCLUSIVE MODE"))

    @staticmethod
    def _physical_paths(file_path: str | None, cog_path: str | None) -> set[Path]:
        """Resolve public COG URLs and restrict cleanup to managed storage roots."""
        roots = [(STORAGE_DIR / name).resolve() for name in ("raw", "cog")]
        paths = set()
        for value in (file_path, cog_path):
            if not value:
                continue
            normalized = str(value).replace("\\", "/")
            if normalized.startswith("/data/"):
                path = STORAGE_DIR / "cog" / normalized[len("/data/"):]
            else:
                path = Path(value)
                if not path.is_absolute():
                    path = STORAGE_DIR.parent / path
            path = path.resolve()
            if any(path.is_relative_to(root) and path != root for root in roots):
                paths.add(path)
        return paths

    @staticmethod
    async def _cleanup_unreferenced_files(db: AsyncSession, paths: set[Path]):
        if not paths:
            return
        try:
            # The metadata deletion is already committed. Recheck references while
            # holding a write lock so an insert cannot race the filesystem cleanup.
            await RasterCRUD.lock_raster_writes(db)
            result = await db.execute(select(RasterMetadata.file_path, RasterMetadata.cog_path))
            referenced = set()
            for file_path, cog_path in result.all():
                referenced.update(RasterCRUD._physical_paths(file_path, cog_path))
            cleanup = asyncio.create_task(asyncio.to_thread(RasterCRUD._delete_paths, paths - referenced))
            try:
                await asyncio.shield(cleanup)
            except asyncio.CancelledError:
                # Cancelling a request does not stop its filesystem thread. Keep
                # the write lock until that thread finishes, then propagate it.
                await cleanup
                raise
        except Exception:
            # Failed cleanup must leave files intact rather than undoing a
            # successful metadata deletion or deleting files without checking.
            logger.exception("Unable to clean up unreferenced raster files")
        finally:
            await db.rollback()  # Release the cleanup transaction's table lock.

    @staticmethod
    def _delete_paths(paths: set[Path]):
        for path in paths:
            RasterCRUD._delete_file(str(path))

    @staticmethod
    def _delete_file(path: str):
        """safely delete files"""
        if not path:
            return
        try:
            os.remove(path)
            logger.info(f"Deleted file: {path}")
        except FileNotFoundError:
            pass
        except Exception as e:
            logger.error(f"Failed to delete file {path}: {e}")

    @staticmethod
    async def update_raster(db: AsyncSession, raster_id: int, update_dict: dict) -> Optional[RasterMetadata]:
        """
        by index_id update raster metadata(only update provided fields)
        used for AI Modify text"overwrite"branch
        """
        stmt = select(RasterMetadata).where(RasterMetadata.index_id == raster_id)
        result = await db.execute(stmt)
        raster = result.scalar_one_or_none()

        if not raster:
            return None

        # only update update_dict fields present in,prevent accidentally clearing other fields
        for key, value in update_dict.items():
            if hasattr(raster, key):
                setattr(raster, key, value)

        await db.commit()
        await db.refresh(raster)
        return raster
