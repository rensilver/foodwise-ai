"""cleanup

Revision ID: 0007_cleanup
Revises: 0006_versions
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007_cleanup"
down_revision: str | Sequence[str] | None = "0006_versions"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "media_cleanup_jobs",
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "storage_key ~ '^[A-Za-z0-9][A-Za-z0-9_.-]*$'",
            name=op.f("ck_media_cleanup_jobs_storage_key_basename"),
        ),
        sa.PrimaryKeyConstraint("storage_key", name=op.f("pk_media_cleanup_jobs")),
    )


def downgrade() -> None:
    op.drop_table("media_cleanup_jobs")
