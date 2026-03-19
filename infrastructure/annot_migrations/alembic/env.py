import sys
import os
import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import async_engine_from_config
from alembic import context

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
if BASE_DIR not in sys.path:
    sys.path.append(BASE_DIR)

from services.annotation_service.models.feature import Base
from services.annotation_service.database import DATABASE_URL

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """过滤 PostGIS 系统表和空间索引"""
    IGNORABLE_TABLES = {
        "spatial_ref_sys", "geometry_columns", "geography_columns",
        "raster_columns", "raster_overviews", "topology", "layer"
    }
    IGNORABLE_PREFIXES = (
        "tiger_", "addr_", "edges_", "faces_", "county_",
        "state_", "place_", "zip_", "tract_", "bg_", "tabblock_",
        "pagc_", "census_"
    )

    if type_ == "table":
        if name in IGNORABLE_TABLES or name.startswith(IGNORABLE_PREFIXES):
            return False

    if type_ == "index":
        if reflected and name and name.startswith("idx_"):
            return False

    return True


def include_name(name, type_, parent_names):
    """
    正确签名：(name, type_, parent_names)
    type_ 可能是 "schema" / "table" / "column" 等。
    只放行 public schema，过滤掉 tiger / topology 等 PostGIS 附带 schema。
    """
    if type_ == "schema":
        return name in ("public", None)
    return True


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object,
        include_schemas=True,       # 扫描带 schema 前缀的表
        include_name=include_name,  # 只扫描 public schema
        transactional_ddl=True,
        render_as_batch=True,
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = DATABASE_URL

    connectable = async_engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_offline() -> None:
    url = DATABASE_URL
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object,
        include_schemas=True,
        include_name=include_name,
    )

    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    try:
        asyncio.run(run_migrations_online())
    except Exception as e:
        print(f"CRITICAL: Migration failed: {e}")
        sys.exit(1)