"""Source artifacts, raw records, document and media provenance.

Revision ID: 0002_provenance
Revises: 0001_catalog
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_provenance"
down_revision: str | Sequence[str] | None = "0001_catalog"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("logical_source_id", sa.Text(), nullable=False),
        sa.Column("locator_kind", sa.Text(), nullable=False),
        sa.Column("locator", sa.Text(), nullable=False),
        sa.Column("published_on", sa.Date(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_sources_content_hash_sha256"),
        ),
        sa.CheckConstraint("id ~ '[^[:space:]]'", name=op.f("ck_sources_id_nonempty")),
        sa.CheckConstraint(
            "locator ~ '[^[:space:]]'", name=op.f("ck_sources_locator_nonempty")
        ),
        sa.CheckConstraint(
            "locator_kind IN ('file', 'url', 'admin')",
            name=op.f("ck_sources_locator_kind_values"),
        ),
        sa.CheckConstraint(
            "logical_source_id ~ '[^[:space:]]'",
            name=op.f("ck_sources_logical_source_id_nonempty"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_sources")),
        sa.UniqueConstraint(
            "logical_source_id",
            "locator_kind",
            "locator",
            "content_hash",
            name=op.f("uq_sources_logical_source_id"),
        ),
    )
    op.create_table(
        "source_records",
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("record_type", sa.Text(), nullable=False),
        sa.Column("record_id", sa.Text(), nullable=False),
        sa.Column(
            "raw_payload",
            postgresql.JSONB(none_as_null=True),
            nullable=True,
        ),
        sa.Column("raw_text", sa.Text(), nullable=True),
        sa.Column("restaurant_id", sa.Text(), nullable=True),
        sa.Column("recipe_id", sa.Text(), nullable=True),
        sa.Column("review_id", sa.Text(), nullable=True),
        sa.Column("ingestion_version", sa.Text(), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("generator", sa.Text(), nullable=True),
        sa.Column("generator_revision", sa.Text(), nullable=True),
        sa.Column("input_hash", sa.Text(), nullable=True),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attribution <> 'generated' OR (generator IS NOT NULL AND input_hash IS NOT NULL)",
            name=op.f("ck_source_records_generation_provenance"),
        ),
        sa.CheckConstraint(
            "attribution IN ('source', 'imported', 'generated')",
            name=op.f("ck_source_records_attribution_values"),
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_source_records_content_hash_sha256"),
        ),
        sa.CheckConstraint(
            "generator ~ '[^[:space:]]'",
            name=op.f("ck_source_records_generator_nonempty"),
        ),
        sa.CheckConstraint(
            "generator_revision ~ '[^[:space:]]'",
            name=op.f("ck_source_records_generator_revision_nonempty"),
        ),
        sa.CheckConstraint(
            "id ~ '[^[:space:]]'", name=op.f("ck_source_records_id_nonempty")
        ),
        sa.CheckConstraint(
            "ingestion_version ~ '[^[:space:]]'",
            name=op.f("ck_source_records_ingestion_version_nonempty"),
        ),
        sa.CheckConstraint(
            "input_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_source_records_input_hash_sha256"),
        ),
        sa.CheckConstraint(
            "recipe_id IS NULL OR record_type = 'recipe'",
            name=op.f("ck_source_records_recipe_type"),
        ),
        sa.CheckConstraint(
            "record_id ~ '[^[:space:]]'",
            name=op.f("ck_source_records_record_id_nonempty"),
        ),
        sa.CheckConstraint(
            "record_type IN ('restaurant', 'recipe', 'review')",
            name=op.f("ck_source_records_record_type_values"),
        ),
        sa.CheckConstraint(
            "restaurant_id IS NULL OR record_type = 'restaurant'",
            name=op.f("ck_source_records_restaurant_type"),
        ),
        sa.CheckConstraint(
            "review_id IS NULL OR record_type = 'review'",
            name=op.f("ck_source_records_review_type"),
        ),
        sa.CheckConstraint(
            "num_nonnulls(restaurant_id, recipe_id, review_id) <= 1",
            name=op.f("ck_source_records_single_entity"),
        ),
        sa.CheckConstraint(
            "raw_payload IS NOT NULL OR raw_text IS NOT NULL",
            name=op.f("ck_source_records_raw_content_required"),
        ),
        sa.ForeignKeyConstraint(
            ["recipe_id"],
            ["recipes.id"],
            name=op.f("fk_source_records_recipe_id_recipes"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["restaurant_id"],
            ["restaurants.id"],
            name=op.f("fk_source_records_restaurant_id_restaurants"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"],
            ["reviews.id"],
            name=op.f("fk_source_records_review_id_reviews"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_id"],
            ["sources.id"],
            name=op.f("fk_source_records_source_id_sources"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_source_records")),
        sa.UniqueConstraint(
            "source_id",
            "record_type",
            "record_id",
            name=op.f("uq_source_records_source_id"),
        ),
    )
    op.create_table(
        "media",
        sa.Column("source_record_id", sa.Text(), nullable=False),
        sa.Column("storage_key", sa.Text(), nullable=False),
        sa.Column("original_locator", sa.Text(), nullable=True),
        sa.Column("mime_type", sa.Text(), nullable=False),
        sa.Column("byte_size", sa.BigInteger(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("ingestion_version", sa.Text(), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("generator", sa.Text(), nullable=True),
        sa.Column("generator_revision", sa.Text(), nullable=True),
        sa.Column("input_hash", sa.Text(), nullable=True),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attribution <> 'generated' OR (generator IS NOT NULL AND input_hash IS NOT NULL)",
            name=op.f("ck_media_generation_provenance"),
        ),
        sa.CheckConstraint(
            "attribution IN ('source', 'imported', 'generated')",
            name=op.f("ck_media_attribution_values"),
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_media_content_hash_sha256")
        ),
        sa.CheckConstraint(
            "generator ~ '[^[:space:]]'", name=op.f("ck_media_generator_nonempty")
        ),
        sa.CheckConstraint(
            "generator_revision ~ '[^[:space:]]'",
            name=op.f("ck_media_generator_revision_nonempty"),
        ),
        sa.CheckConstraint("id ~ '[^[:space:]]'", name=op.f("ck_media_id_nonempty")),
        sa.CheckConstraint(
            "ingestion_version ~ '[^[:space:]]'",
            name=op.f("ck_media_ingestion_version_nonempty"),
        ),
        sa.CheckConstraint(
            "input_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_media_input_hash_sha256")
        ),
        sa.CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name=op.f("ck_media_mime_type_values"),
        ),
        sa.CheckConstraint(
            "storage_key ~ '^[A-Za-z0-9][A-Za-z0-9_.-]*$'",
            name=op.f("ck_media_storage_key_basename"),
        ),
        sa.CheckConstraint("byte_size > 0", name=op.f("ck_media_byte_size_positive")),
        sa.CheckConstraint(
            "width > 0 AND height > 0", name=op.f("ck_media_dimensions_positive")
        ),
        sa.ForeignKeyConstraint(
            ["source_record_id"],
            ["source_records.id"],
            name=op.f("fk_media_source_record_id_source_records"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_media")),
        sa.CheckConstraint(
            "original_locator ~ '[^[:space:]]'",
            name=op.f("ck_media_original_locator_nonempty"),
        ),
        sa.UniqueConstraint("id", "source_record_id", name=op.f("uq_media_id")),
        sa.UniqueConstraint("storage_key", name=op.f("uq_media_storage_key")),
    )
    op.create_table(
        "documents",
        sa.Column("source_record_id", sa.Text(), nullable=False),
        sa.Column("media_id", sa.Text(), nullable=True),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("start_offset", sa.Integer(), nullable=True),
        sa.Column("end_offset", sa.Integer(), nullable=True),
        sa.Column("ingestion_version", sa.Text(), nullable=False),
        sa.Column("attribution", sa.Text(), nullable=False),
        sa.Column("generator", sa.Text(), nullable=True),
        sa.Column("generator_revision", sa.Text(), nullable=True),
        sa.Column("input_hash", sa.Text(), nullable=True),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("content_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "attribution <> 'generated' OR (generator IS NOT NULL AND input_hash IS NOT NULL)",
            name=op.f("ck_documents_generation_provenance"),
        ),
        sa.CheckConstraint(
            "attribution IN ('source', 'imported', 'generated')",
            name=op.f("ck_documents_attribution_values"),
        ),
        sa.CheckConstraint(
            "content_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_documents_content_hash_sha256"),
        ),
        sa.CheckConstraint(
            "generator ~ '[^[:space:]]'", name=op.f("ck_documents_generator_nonempty")
        ),
        sa.CheckConstraint(
            "generator_revision ~ '[^[:space:]]'",
            name=op.f("ck_documents_generator_revision_nonempty"),
        ),
        sa.CheckConstraint(
            "id ~ '[^[:space:]]'", name=op.f("ck_documents_id_nonempty")
        ),
        sa.CheckConstraint(
            "ingestion_version ~ '[^[:space:]]'",
            name=op.f("ck_documents_ingestion_version_nonempty"),
        ),
        sa.CheckConstraint(
            "input_hash ~ '^[0-9a-f]{64}$'", name=op.f("ck_documents_input_hash_sha256")
        ),
        sa.CheckConstraint(
            "kind ~ '[^[:space:]]'", name=op.f("ck_documents_kind_nonempty")
        ),
        sa.CheckConstraint(
            "text ~ '[^[:space:]]'", name=op.f("ck_documents_text_nonempty")
        ),
        sa.CheckConstraint(
            "(start_offset IS NULL AND end_offset IS NULL) OR (start_offset IS NOT NULL AND end_offset IS NOT NULL AND start_offset >= 0 AND end_offset > start_offset)",
            name=op.f("ck_documents_offset_range"),
        ),
        sa.ForeignKeyConstraint(
            ["media_id", "source_record_id"],
            ["media.id", "media.source_record_id"],
            name=op.f("fk_documents_media_id_media"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["source_record_id"],
            ["source_records.id"],
            name=op.f("fk_documents_source_record_id_source_records"),
            onupdate="RESTRICT",
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_documents")),
    )


def downgrade() -> None:
    op.drop_table("documents")
    op.drop_table("media")
    op.drop_table("source_records")
    op.drop_table("sources")
