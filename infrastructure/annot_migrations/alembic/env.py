import sys
import os
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool, text
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# 1. 动态路径注入，确保多环境下的模块导入
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

# 导入业务模型与配置
from services.annotation_service.models.feature import Base
from services.annotation_service.database import DATABASE_URL

# Alembic 配置对象
config = context.config

# 解释并加载日志配置
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 这里的 target_metadata 包含了所有业务模型 (Project, Layer, Feature)
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """
    工业级过滤器：
    1. 屏蔽 PostGIS/Tiger Geocoder 系统表，防止 Alembic 尝试删除它们。
    2. 屏蔽反映出的 'idx_' 开头的空间索引，防止与模型中的显式定义冲突。
    """
    if type_ == "table":
        # 需要忽略的 PostGIS 及其扩展生成的系统表前缀或全名
        IGNORABLE_TABLES = {
            "spatial_ref_sys", "geometry_columns", "geography_columns",
            "raster_columns", "raster_overviews", "topology", "layer"
        }
        IGNORABLE_PREFIXES = (
            "tiger_", "addr_", "edges_", "faces_", "county_",
            "state_", "place_", "zip_", "tract_", "bg_", "tabblock_",
            "pagc_", "census_"
        )

        if name in IGNORABLE_TABLES or name.startswith(IGNORABLE_PREFIXES):
            return False

    if type_ == "index":
        # 如果是数据库中已存在的 (reflected) 且以 idx_ 开头的索引，
        # 我们让 Alembic 忽略它，转而信任模型中显式定义的 Index。
        if reflected and name and name.startswith("idx_"):
            return False

    return True


def do_run_migrations(connection):
    """同步执行迁移的任务函数"""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        # 工业实践：确保 DDL 操作在事务中，失败则全量回滚
        transactional_ddl=True,
        # 允许在 alembic_version 表上使用 batch 模式（增强兼容性）
        render_as_batch=True,
        # 捕获类型变更（如 String 长度变化）
        compare_type=True,
        # 捕获默认值变更
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """以异步方式连接数据库并运行迁移"""
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = DATABASE_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        # 使用 run_sync 执行同步的迁移逻辑
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    """离线生成 SQL 脚本模式"""
    url = DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
    )

    with context.begin_transaction():
        context.run_migrations()


# 执行逻辑入口
if context.is_offline_mode():
    run_migrations_offline()
else:
    try:
        asyncio.run(run_migrations_online())
    except Exception as e:
        print(f"CRITICAL: Migration failed: {e}")
        sys.exit(1)