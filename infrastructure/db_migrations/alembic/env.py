import asyncio
from logging.config import fileConfig
from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

# 1. 动态导入项目根目录
# 这样无论在哪个目录下运行 alembic，都能正确找到 services 模块
import sys
import os

# 获取当前文件的绝对路径，并向上推三级到达项目根目录 (F:\rsmarking)
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
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """
    通过此钩子函数过滤掉非本项目的数据库对象。
    解决 PostGIS、Tiger Geocoder 等扩展生成的系统表干扰迁移的问题。
    """
    if type_ == "table":
        # 1. 核心业务表白名单：只允许这些表出现在迁移脚本中
        # 如果你的业务表增加了，请在这里补充
        allowed_tables = ["raster_metadata"]
        if name in allowed_tables:
            return True

        # 2. 模式过滤：通常扩展表会带有一些固定的前缀
        # 我们屏蔽掉所有 PostGIS 常见的系统表和 Tiger Geocoder 的前缀
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
            return False

    return True

def run_migrations_offline() -> None:
    """脱机模式迁移"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object  # 应用过滤器
    )

    with context.begin_transaction():
        context.run_migrations()

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