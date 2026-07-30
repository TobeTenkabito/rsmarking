"""add raster temporal and product metadata

Revision ID: 2c7e6a9d4b10
Revises: 8f2b6d4c9a11
Create Date: 2026-07-30 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "2c7e6a9d4b10"
down_revision: Union[str, None] = "8f2b6d4c9a11"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "raster_metadata",
        sa.Column("acquired_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "raster_metadata",
        sa.Column("acquired_at_end", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "raster_metadata",
        sa.Column(
            "acquired_at_source",
            sa.String(length=32),
            nullable=False,
            server_default="unknown",
        ),
    )
    op.add_column(
        "raster_metadata",
        sa.Column(
            "acquired_at_confidence",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "raster_metadata",
        sa.Column("platform", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "raster_metadata",
        sa.Column("sensor", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "raster_metadata",
        sa.Column("product_id", sa.String(length=255), nullable=True),
    )
    op.add_column(
        "raster_metadata",
        sa.Column("processing_level", sa.String(length=100), nullable=True),
    )
    op.add_column(
        "raster_metadata",
        sa.Column("tile_id", sa.String(length=100), nullable=True),
    )
    op.create_index(
        "ix_raster_metadata_acquired_at",
        "raster_metadata",
        ["acquired_at"],
        unique=False,
    )
    op.create_index(
        "ix_raster_metadata_product_id",
        "raster_metadata",
        ["product_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(
        "ix_raster_metadata_product_id",
        table_name="raster_metadata",
    )
    op.drop_index(
        "ix_raster_metadata_acquired_at",
        table_name="raster_metadata",
    )
    op.drop_column("raster_metadata", "tile_id")
    op.drop_column("raster_metadata", "processing_level")
    op.drop_column("raster_metadata", "product_id")
    op.drop_column("raster_metadata", "sensor")
    op.drop_column("raster_metadata", "platform")
    op.drop_column("raster_metadata", "acquired_at_confidence")
    op.drop_column("raster_metadata", "acquired_at_source")
    op.drop_column("raster_metadata", "acquired_at_end")
    op.drop_column("raster_metadata", "acquired_at")
