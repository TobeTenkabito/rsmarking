"""create_task_jobs_table

Revision ID: 8f2b6d4c9a11
Revises: 44e5a475e0a1
Create Date: 2026-05-10 09:20:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f2b6d4c9a11"
down_revision: Union[str, None] = "44e5a475e0a1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "task_jobs",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("job_id", sa.String(length=64), nullable=False),
        sa.Column("celery_task_id", sa.String(length=64), nullable=True),
        sa.Column("task_type", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("raster_index_id", sa.String(length=32), nullable=True),
        sa.Column("params", sa.JSON(), nullable=True),
        sa.Column("result", sa.JSON(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("job_id", name="uq_task_jobs_job_id"),
    )
    op.create_index("ix_task_jobs_job_id", "task_jobs", ["job_id"], unique=True)
    op.create_index("ix_task_jobs_index_id", "task_jobs", ["raster_index_id"], unique=False)
    op.create_index("ix_task_jobs_status", "task_jobs", ["status"], unique=False)
    op.create_index("ix_task_jobs_created_at", "task_jobs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_jobs_created_at", table_name="task_jobs")
    op.drop_index("ix_task_jobs_status", table_name="task_jobs")
    op.drop_index("ix_task_jobs_index_id", table_name="task_jobs")
    op.drop_index("ix_task_jobs_job_id", table_name="task_jobs")
    op.drop_table("task_jobs")
