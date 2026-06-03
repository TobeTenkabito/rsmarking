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
    print(f"DEBUG: table: {list(Base.metadata.tables.keys())}")
except ImportError as e:
    print(f"Error: text.text: {root_dir}")
    print(f"text: {e}")
    sys.exit(1)


# Alembic Config object
config = context.config

# text
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# 2. text,used for --autogenerate table
target_metadata = Base.metadata


def include_object(object, name, type_, reflected, compare_to):
    """
    throughdatabaseobject.
    text PostGIS,Tiger Geocoder table.
    """
    if type_ == "table":
        # 1. table:table
        # tableadded,text
        allowed_tables = ["raster_metadata"]
        if name in allowed_tables:
            return True

        # 2. text:table
        # text PostGIS table Tiger Geocoder text
        ignored_prefixes = (
            "spatial_", "geometry_", "geography_", "raster_",  # PostGIS text
            "tiger", "addr", "edges", "faces", "county",  # Tiger Geocoder
            "state", "place", "zip", "tract", "bg", "tabblock",
            "pagc_", "census_"  # text
        )

        if name.startswith(ignored_prefixes):
            return False

        # 3. text:table 'public' text schema
        # text reflected table
        if reflected and name not in allowed_tables:
            return False

    return True


def run_migrations_offline() -> None:
    """text"""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        include_object=include_object  # text
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        include_object=include_object  # text
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """text(async)"""
    # from alembic.ini text URL
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
    # text Windows async
    try:
        asyncio.run(run_migrations_online())
    except (KeyboardInterrupt, SystemExit):
        pass