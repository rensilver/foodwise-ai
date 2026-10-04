"""Revocable local administrator sessions.

Revision ID: 0009_admin
Revises: 0008_ingestion
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_admin"
down_revision = "0008_ingestion"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_sessions",
        sa.Column("token_hash", sa.Text(), primary_key=True),
        sa.Column("csrf_hash", sa.Text(), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_admin_sessions_token_hash_sha256"),
        ),
        sa.CheckConstraint(
            "csrf_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_admin_sessions_csrf_hash_sha256"),
        ),
    )


def downgrade() -> None:
    op.drop_table("admin_sessions")
