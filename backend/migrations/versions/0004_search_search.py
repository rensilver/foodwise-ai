"""search

Revision ID: 0004_search
Revises: 0003_embeddings
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004_search"
down_revision: str | Sequence[str] | None = "0003_embeddings"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "documents",
        sa.Column(
            "search_vector",
            postgresql.TSVECTOR(),
            sa.Computed("to_tsvector('english'::regconfig, text)", persisted=True),
            nullable=False,
        ),
    )
    op.create_index(
        "ix_documents_search",
        "documents",
        ["search_vector"],
        unique=False,
        postgresql_using="gin",
    )
    op.create_index(
        "ix_documents_source_record", "documents", ["source_record_id"], unique=False
    )
    op.create_index(
        "ix_media_source_record", "media", ["source_record_id"], unique=False
    )
    op.create_index(
        "ix_recipes_cuisine", "recipes", ["normalized_cuisine"], unique=False
    )
    op.create_index(
        "ix_restaurants_filters",
        "restaurants",
        ["normalized_cuisine", "normalized_location", "price_band"],
        unique=False,
    )
    op.create_index(
        "ix_restaurants_location_price",
        "restaurants",
        ["normalized_location", "price_band"],
        unique=False,
    )
    op.create_index(
        "ix_reviews_profile_restaurant",
        "reviews",
        ["demo_profile_id", "restaurant_id"],
        unique=False,
    )
    op.create_index(
        "ix_source_records_recipe", "source_records", ["recipe_id"], unique=False
    )
    op.create_index(
        "ix_source_records_restaurant",
        "source_records",
        ["restaurant_id"],
        unique=False,
    )
    op.create_index(
        "ix_source_records_review", "source_records", ["review_id"], unique=False
    )


def downgrade() -> None:
    op.drop_index("ix_source_records_review", table_name="source_records")
    op.drop_index("ix_source_records_restaurant", table_name="source_records")
    op.drop_index("ix_source_records_recipe", table_name="source_records")
    op.drop_index("ix_reviews_profile_restaurant", table_name="reviews")
    op.drop_index("ix_restaurants_location_price", table_name="restaurants")
    op.drop_index("ix_restaurants_filters", table_name="restaurants")
    op.drop_index("ix_recipes_cuisine", table_name="recipes")
    op.drop_index("ix_media_source_record", table_name="media")
    op.drop_index("ix_documents_source_record", table_name="documents")
    op.drop_index("ix_documents_search", table_name="documents", postgresql_using="gin")
    op.drop_column("documents", "search_vector")
