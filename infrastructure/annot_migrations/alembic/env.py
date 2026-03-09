<<<<<<< HEAD
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
=======
import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context


import sys
import os


current_dir = os.path.dirname(os.path.realpath(__file__))
root_dir = os.path.abspath(os.path.join(current_dir, '..', '..', '..'))

if root_dir not in sys.path:
    sys.path.insert(0, root_dir)


try:
    from services.data_service.models import Base
    print(f"DEBUG: 检测到的模型表: {list(Base.metadata.tables.keys())}")
except ImportError as e:
    print(f"Error: 无法导入模型。当前根目录: {root_dir}")
    print(f"详细错误: {e}")
    sys.exit(1)


# Alembic Config 对象
config = context.config

# 配置日志
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. 设置元数据，用于 --autogenerate 自动检测表结构变化
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """
<<<<<<< HEAD
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
=======
    通过此钩子函数过滤掉非本项目的数据库对象。
    解决 PostGIS、Tiger Geocoder 等扩展生成的系统表干扰迁移的问题。
    """
    if type_ == "table":
        # 1. 核心业务表白名单：只允许这些表出现在迁移脚本中
        allowed_tables = ["raster_metadata"]
        if name in allowed_tables:
            return True

        # 2. 模式过滤：通常扩展表会带有一些固定的前缀
        ignored_prefixes = (
            "spatial_", "geometry_", "geography_", "raster_",  # PostGIS 核心
            "tiger", "addr", "edges", "faces", "county",  # Tiger Geocoder
            "state", "place", "zip", "tract", "bg", "tabblock",
            "pagc_", "census_"  # 辅助工具
        )

        if name.startswith(ignored_prefixes):
            return False

        # 3. 额外保险：如果你确定你的业务表不属于 'public' 以外的 schema
        # 或者你只想处理特定的 reflected 表
        if reflected and name not in allowed_tables:
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
            return False

    return True


<<<<<<< HEAD
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
=======
def run_migrations_offline() -> None:
    """脱机模式迁移"""
    url = config.get_main_option("sqlalchemy.url")
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
<<<<<<< HEAD
        include_object=include_object,
=======
        include_object=include_object  # 应用过滤器
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
    )

    with context.begin_transaction():
        context.run_migrations()


<<<<<<< HEAD
# 执行逻辑入口
if context.is_offline_mode():
    run_migrations_offline()
else:
    try:
        asyncio.run(run_migrations_online())
    except Exception as e:
        print(f"CRITICAL: Migration failed: {e}")
        sys.exit(1)
=======
def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object  # 应用过滤器
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """联机模式迁移（处理异步引擎）"""
    # 允许从 alembic.ini 或环境变量获取 URL
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()

if context.is_offline_mode():
    run_migrations_offline()
else:
    # 确保在 Windows 环境下正确处理异步事件循环
    try:
        asyncio.run(run_migrations_online())
    except (KeyboardInterrupt, SystemExit):
        pass
>>>>>>> bd05e13daabf3cba3f74fa7d9fbf6191d3065cfd
