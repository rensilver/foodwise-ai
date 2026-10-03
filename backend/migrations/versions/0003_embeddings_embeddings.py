"""embeddings

Revision ID: 0003_embeddings
Revises: 0002_provenance
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from pgvector.sqlalchemy import Vector

revision: str = "0003_embeddings"
down_revision: str | Sequence[str] | None = "0002_provenance"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.create_table(
        "image_embeddings",
        sa.Column("media_id", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(dim=512), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("revision", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "id ~ '[^[:space:]]'", name=op.f("ck_image_embeddings_id_nonempty")
        ),
        sa.CheckConstraint(
            "input_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_image_embeddings_input_hash_sha256"),
        ),
        sa.CheckConstraint(
            "model = 'openai/clip-vit-base-patch32'",
            name=op.f("ck_image_embeddings_model_identity"),
        ),
        sa.CheckConstraint(
            "revision ~ '[^[:space:]]'",
            name=op.f("ck_image_embeddings_revision_nonempty"),
        ),
        sa.CheckConstraint(
            "dimension = 512", name=op.f("ck_image_embeddings_dimension_value")
        ),
        sa.CheckConstraint(
            "vector_norm(embedding) BETWEEN 0.999 AND 1.001",
            name=op.f("ck_image_embeddings_normalized_vector"),
        ),
        sa.ForeignKeyConstraint(
            ["media_id"],
            ["media.id"],
            name=op.f("fk_image_embeddings_media_id_media"),
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_image_embeddings")),
        sa.UniqueConstraint(
            "media_id", "model", "revision", name=op.f("uq_image_embeddings_media_id")
        ),
    )
    op.create_table(
        "text_embeddings",
        sa.Column("document_id", sa.Text(), nullable=False),
        sa.Column("embedding", Vector(dim=384), nullable=False),
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("model", sa.Text(), nullable=False),
        sa.Column("revision", sa.Text(), nullable=False),
        sa.Column("input_hash", sa.Text(), nullable=False),
        sa.Column("dimension", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "id ~ '[^[:space:]]'", name=op.f("ck_text_embeddings_id_nonempty")
        ),
        sa.CheckConstraint(
            "input_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_text_embeddings_input_hash_sha256"),
        ),
        sa.CheckConstraint(
            "model = 'sentence-transformers/all-MiniLM-L6-v2'",
            name=op.f("ck_text_embeddings_model_identity"),
        ),
        sa.CheckConstraint(
            "revision ~ '[^[:space:]]'",
            name=op.f("ck_text_embeddings_revision_nonempty"),
        ),
        sa.CheckConstraint(
            "dimension = 384", name=op.f("ck_text_embeddings_dimension_value")
        ),
        sa.CheckConstraint(
            "vector_norm(embedding) BETWEEN 0.999 AND 1.001",
            name=op.f("ck_text_embeddings_normalized_vector"),
        ),
        sa.ForeignKeyConstraint(
            ["document_id"],
            ["documents.id"],
            name=op.f("fk_text_embeddings_document_id_documents"),
            onupdate="RESTRICT",
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_text_embeddings")),
        sa.UniqueConstraint(
            "document_id",
            "model",
            "revision",
            name=op.f("uq_text_embeddings_document_id"),
        ),
    )


def downgrade() -> None:
    op.drop_table("text_embeddings")
    op.drop_table("image_embeddings")
