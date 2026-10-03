"""Stable restaurant, recipe and review identities with nullable metadata.

Revision ID: 0001_catalog
Revises: None
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_catalog"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _identity(table: str) -> list[sa.Column | sa.Constraint]:
    return [
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("source_record_id", sa.Text(), nullable=False),
        sa.PrimaryKeyConstraint("id", name=f"pk_{table}"),
        sa.UniqueConstraint(
            "source_id", "source_record_id", name=f"uq_{table}_source_id"
        ),
        *(
            sa.CheckConstraint(
                f"{column} ~ '[^[:space:]]'", name=f"ck_{table}_{column}_nonempty"
            )
            for column in ("id", "source_id", "source_record_id")
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "restaurants",
        *_identity("restaurants"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("cuisine", sa.Text(), nullable=True),
        sa.Column("normalized_cuisine", sa.Text(), nullable=True),
        sa.Column("location", sa.Text(), nullable=True),
        sa.Column("normalized_location", sa.Text(), nullable=True),
        sa.Column("restaurant_type", sa.Text(), nullable=True),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("price_band", sa.Integer(), nullable=True),
        sa.Column("signatures", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("vibe", sa.Text(), nullable=True),
        sa.Column("environment", sa.Text(), nullable=True),
        sa.Column("shortcomings", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("availability", sa.Text(), nullable=True),
        sa.Column("latitude", sa.Float(), nullable=True),
        sa.Column("longitude", sa.Float(), nullable=True),
        sa.Column("allergens", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.CheckConstraint(
            "name ~ '[^[:space:]]'", name="ck_restaurants_name_nonempty"
        ),
        sa.CheckConstraint(
            "price_band BETWEEN 1 AND 4", name="ck_restaurants_price_band_range"
        ),
        sa.CheckConstraint(
            "rating BETWEEN 0 AND 5", name="ck_restaurants_rating_range"
        ),
        sa.CheckConstraint(
            "latitude BETWEEN -90 AND 90", name="ck_restaurants_latitude_range"
        ),
        sa.CheckConstraint(
            "longitude BETWEEN -180 AND 180", name="ck_restaurants_longitude_range"
        ),
    )
    op.create_table(
        "recipes",
        *_identity("recipes"),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("cuisine", sa.Text(), nullable=True),
        sa.Column("normalized_cuisine", sa.Text(), nullable=True),
        sa.Column("servings", sa.Integer(), nullable=True),
        sa.Column("prep_time", sa.Text(), nullable=True),
        sa.Column("cook_time", sa.Text(), nullable=True),
        sa.Column("total_time", sa.Text(), nullable=True),
        sa.Column("ingredients", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("directions", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.Column("difficulty", sa.Text(), nullable=True),
        sa.Column("nutrition", postgresql.JSONB(), nullable=True),
        sa.Column("availability", sa.Text(), nullable=True),
        sa.Column("allergens", postgresql.ARRAY(sa.Text()), nullable=True),
        sa.CheckConstraint("name ~ '[^[:space:]]'", name="ck_recipes_name_nonempty"),
        sa.CheckConstraint("servings > 0", name="ck_recipes_servings_positive"),
    )
    op.create_table(
        "reviews",
        *_identity("reviews"),
        sa.Column("restaurant_id", sa.Text(), nullable=False),
        sa.Column("demo_profile_id", sa.Text(), nullable=False),
        sa.Column("title", sa.Text(), nullable=True),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("rating", sa.Float(), nullable=True),
        sa.Column("published_on", sa.Date(), nullable=True),
        sa.Column("language", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(
            ["restaurant_id"],
            ["restaurants.id"],
            name="fk_reviews_restaurant_id_restaurants",
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        sa.CheckConstraint(
            "demo_profile_id ~ '[^[:space:]]'",
            name="ck_reviews_demo_profile_id_nonempty",
        ),
        sa.CheckConstraint("text ~ '[^[:space:]]'", name="ck_reviews_text_nonempty"),
        sa.CheckConstraint("rating BETWEEN 0 AND 5", name="ck_reviews_rating_range"),
    )


def downgrade() -> None:
    op.drop_table("reviews")
    op.drop_table("recipes")
    op.drop_table("restaurants")
