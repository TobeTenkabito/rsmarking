"""
Worker 层数据模型
task_jobs 表：记录所有异步任务的生命周期
使用 data_service 同一个 Base，迁移时统一管理。
"""
import enum
from datetime import datetime, timezone

from sqlalchemy import (
    Column, String, Integer, DateTime, JSON, Text, Enum as SAEnum, Index,
)
from sqlalchemy.ext.declarative import declarative_base

# 独立 Base，不与 data_service 的 Base 混用，
# 避免 Worker 进程意外触发 data_service 的表创建
Base = declarative_base()


class TaskStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRYING = "retrying"
    REVOKED = "revoked"


class TaskType(str, enum.Enum):
    # 预处理
    BUILD_PYRAMID = "build_pyramid"
    REPROJECT = "reproject"
    COMPUTE_STATS = "compute_stats"
    CONVERT_COG = "convert_cog"
    # 指数计算
    CALC_INDEX = "calc_index"
    CALC_CUSTOM = "calc_custom"
    # 提取
    EXTRACT_FEATURE = "extract_feature"
    # 裁剪
    CLIP_RASTER = "clip_raster"
    # 导出
    EXPORT_GEOJSON = "export_geojson"
    EXPORT_COCO = "export_coco"
    EXPORT_TFRECORD = "export_tfrecord"


class TaskJob(Base):
    """
    异步任务记录表
    job_id      : 业务侧生成的 UUID，前端用此 ID 轮询状态
    celery_task_id : Celery 内部 task_id，用于 revoke
    """
    __tablename__ = "task_jobs"
    __table_args__ = (
        Index("ix_task_jobs_index_id",  "raster_index_id"),
        Index("ix_task_jobs_status",    "status"),
        Index("ix_task_jobs_created_at","created_at"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(64),  unique=True, nullable=False, index=True)
    celery_task_id = Column(String(64),  nullable=True)

    task_type = Column(String(64),  nullable=False)   # TaskType 枚举值
    status = Column(String(16),  nullable=False,
                            default=TaskStatus.PENDING.value)

    # 关联的栅格（可为空，导出任务可能不关联单个栅格）
    raster_index_id = Column(String(32), nullable=True)

    # 任务入参快照（方便排查问题）
    params = Column(JSON,  nullable=True)

    # 结果元数据（如生成文件的 index_id、路径等）
    result = Column(JSON,  nullable=True)

    # 错误信息
    error = Column(Text,  nullable=True)

    # 重试次数
    retry_count = Column(Integer, default=0)

    # 时间戳
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
