import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from typing import List, Optional
from services.data_service.models import RasterMetadata

logger = logging.getLogger("data_service.crud")


class RasterCRUD:

    @staticmethod
    async def create_raster(db: AsyncSession, metadata_dict: dict):
        """保存影像元数据"""
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
            resolution_y=res_y
        )
        db.add(db_obj)
        await db.flush()
        return db_obj

    @staticmethod
    async def get_all_rasters(db: AsyncSession) -> List[RasterMetadata]:
        """获取所有影像"""
        stmt = select(RasterMetadata).order_by(RasterMetadata.created_at.desc())
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_raster_by_index_id(db: AsyncSession, raster_id: int) -> Optional[RasterMetadata]:
        """根据数据库主键ID获取单个影像记录"""
        stmt = select(RasterMetadata).where(RasterMetadata.index_id == raster_id)
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_rasters_by_bundle(db: AsyncSession, bundle_id: str) -> List[RasterMetadata]:
        """根据bundle_id查询"""
        stmt = select(RasterMetadata).where(RasterMetadata.bundle_id == bundle_id)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def delete_raster(db: AsyncSession, raster_id: int) -> bool:
        """删除单个影像"""
        stmt = select(RasterMetadata).where(RasterMetadata.id == raster_id)
        result = await db.execute(stmt)
        raster = result.scalar_one_or_none()
        if not raster:
            return False
        RasterCRUD._delete_physical_files(raster)
        await db.delete(raster)
        await db.commit()
        return True

    @staticmethod
    async def clear_all_rasters(db: AsyncSession) -> bool:
        """清空数据库并删除所有文件"""
        stmt = select(RasterMetadata.file_path, RasterMetadata.cog_path)
        result = await db.execute(stmt)
        rows = result.all()
        for file_path, cog_path in rows:
            RasterCRUD._delete_file(file_path)
            if cog_path:
                cog_filename = os.path.basename(cog_path)
                cog_dir = os.path.dirname(file_path).replace(os.sep + "raw", os.sep + "cog")
                full_cog_path = os.path.join(cog_dir, cog_filename)
                RasterCRUD._delete_file(full_cog_path)
        await db.execute(delete(RasterMetadata))
        await db.commit()
        logger.info("Database and physical files cleared.")
        return True

    @staticmethod
    def _delete_file(path: str):
        """安全删除文件"""
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
    def _delete_physical_files(raster: RasterMetadata):
        """删除原始文件和COG"""
        RasterCRUD._delete_file(raster.file_path)
        if raster.cog_path:
            cog_filename = os.path.basename(raster.cog_path)
            cog_dir = os.path.dirname(raster.file_path).replace(os.sep + "raw", os.sep + "cog")
            full_cog_path = os.path.join(cog_dir, cog_filename)
            RasterCRUD._delete_file(full_cog_path)

    @staticmethod
    async def update_raster(db: AsyncSession, raster_id: int, update_dict: dict) -> Optional[RasterMetadata]:
        """
        根据 index_id 更新栅格元数据（仅更新传入的字段）
        用于 AI Modify 模式的"覆盖"分支
        """
        stmt = select(RasterMetadata).where(RasterMetadata.index_id == raster_id)
        result = await db.execute(stmt)
        raster = result.scalar_one_or_none()

        if not raster:
            return None

        # 只更新 update_dict 中存在的字段，防止意外清空其他字段
        for key, value in update_dict.items():
            if hasattr(raster, key):
                setattr(raster, key, value)

        await db.commit()
        await db.refresh(raster)
        return raster
