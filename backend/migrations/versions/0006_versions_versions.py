"""versions

Revision ID: 0006_versions
Revises: 0005_context
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0006_versions"
down_revision: str | Sequence[str] | None = "0005_context"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "recipes",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column(
        "restaurants",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )
    op.add_column(
        "reviews",
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    )

    for table in ("restaurants", "recipes", "reviews"):
        op.create_check_constraint(
            op.f(f"ck_{table}_version_positive"), table, "version > 0"
        )


def downgrade() -> None:
    for table in ("restaurants", "recipes", "reviews"):
        op.drop_constraint(op.f(f"ck_{table}_version_positive"), table, type_="check")
    op.drop_column("reviews", "version")
    op.drop_column("restaurants", "version")
    op.drop_column("recipes", "version")
