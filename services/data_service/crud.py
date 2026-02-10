import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import delete
from .models import RasterMetadata

logger = logging.getLogger("data_service.crud")


class RasterCRUD:
    @staticmethod
    async def create_raster(db: AsyncSession, metadata_dict: dict):
        """将解析后的元数据保存到数据库"""

        # 统一 COG 路径获取逻辑
        cog_url = metadata_dict.get("cog_path") or metadata_dict.get("cog_url")

        # 处理分辨率的多种可能格式
        res_x = metadata_dict.get("resolution_x")
        res_y = metadata_dict.get("resolution_y")
        if "resolution" in metadata_dict and (res_x is None or res_y is None):
            res_x = metadata_dict["resolution"][0]
            res_y = metadata_dict["resolution"][1]

        db_obj = RasterMetadata(
            file_name=metadata_dict.get("file_name"),
            bundle_id=metadata_dict.get("bundle_id"),
            index_id=metadata_dict.get("index_id"),  # 新增索引id
            file_path=metadata_dict.get("file_path"),
            cog_path=cog_url,
            crs=metadata_dict.get("crs"),
            bounds=metadata_dict.get("bounds"),
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
    async def get_all_rasters(db: AsyncSession):
        """获取所有影像记录"""
        result = await db.execute(select(RasterMetadata).order_by(RasterMetadata.created_at.desc()))
        return result.scalars().all()


    @staticmethod
    async def get_rasters_by_bundle(db: AsyncSession, bundle_id: str):
        """按 bundle_id 获取一组影像"""
        result = await db.execute(
            select(RasterMetadata).where(RasterMetadata.bundle_id == bundle_id)
        )
        return result.scalars().all()

    @staticmethod
    async def delete_raster(db: AsyncSession, raster_id: int):
        """删除单条影像记录及其物理文件"""
        result = await db.execute(select(RasterMetadata).where(RasterMetadata.id == raster_id))
        raster = result.scalar_one_or_none()

        if raster:
            # 1. 尝试删除物理文件
            RasterCRUD._delete_physical_files(raster)

            # 2. 删除数据库记录
            await db.delete(raster)
            await db.commit()
            return True
        return False

    @staticmethod
    async def clear_all_rasters(db: AsyncSession):
        """清空数据库并物理删除所有相关文件"""
        # 1. 先查询出所有记录以便获取文件路径
        all_rasters = await RasterCRUD.get_all_rasters(db)

        # 2. 逐一删除物理文件
        for raster in all_rasters:
            RasterCRUD._delete_physical_files(raster)

        # 3. 清空表
        await db.execute(delete(RasterMetadata))
        await db.commit()
        logger.info("Database and physical files cleared.")
        return True

    @staticmethod
    def _delete_physical_files(raster: RasterMetadata):
        """辅助方法：安全删除磁盘上的原始文件和 COG 文件"""
        # 删除原始文件
        if raster.file_path and os.path.exists(raster.file_path):
            try:
                os.remove(raster.file_path)
                logger.info(f"Deleted raw file: {raster.file_path}")
            except Exception as e:
                logger.error(f"Failed to delete raw file {raster.file_path}: {e}")

        # 删除 COG 文件 (注意：数据库存的是 Web 路径 /data/xxx.tif)
        if raster.cog_path:
            base_dir = os.path.dirname(raster.file_path).replace("raw", "cog")
            filename = os.path.basename(raster.cog_path)
            full_cog_path = os.path.join(base_dir, filename)

            if os.path.exists(full_cog_path):
                try:
                    os.remove(full_cog_path)
                    logger.info(f"Deleted COG file: {full_cog_path}")
                except Exception as e:
                    logger.error(f"Failed to delete COG file {full_cog_path}: {e}")