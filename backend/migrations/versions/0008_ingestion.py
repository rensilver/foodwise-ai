"""Atomic seed ingestion checkpoints.

Revision ID: 0008_ingestion
Revises: 0007_cleanup
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0008_ingestion"
down_revision: str | Sequence[str] | None = "0007_cleanup"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_checkpoints",
        sa.Column("category", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Text(), nullable=False),
        sa.Column("fingerprint", sa.Text(), nullable=False),
        sa.Column("ingestion_version", sa.Text(), nullable=False),
        sa.Column("catalog_version", sa.Integer(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "category IN ('restaurant', 'recipe', 'review')",
            name=op.f("ck_ingestion_checkpoints_category_values"),
        ),
        sa.CheckConstraint(
            "entity_id ~ '[^[:space:]]'",
            name=op.f("ck_ingestion_checkpoints_entity_id_nonempty"),
        ),
        sa.CheckConstraint(
            "fingerprint ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_ingestion_checkpoints_fingerprint_sha256"),
        ),
        sa.CheckConstraint(
            "catalog_version > 0",
            name=op.f("ck_ingestion_checkpoints_version_positive"),
        ),
        sa.PrimaryKeyConstraint(
            "category", "entity_id", name=op.f("pk_ingestion_checkpoints")
        ),
    )


def downgrade() -> None:
    op.drop_table("ingestion_checkpoints")
