"""Separate normalized text/image vector tables; no approximate indexes."""

from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Integer,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from food_recommender.infrastructure.persistence.models.base import Base


def constraints(
    parent: str, model: str, dimension: int
) -> tuple[UniqueConstraint | CheckConstraint, ...]:
    return (
        UniqueConstraint(parent, "model", "revision"),
        CheckConstraint(f"model = '{model}'", name="model_identity"),
        CheckConstraint(f"dimension = {dimension}", name="dimension_value"),
        CheckConstraint(
            "vector_norm(embedding) BETWEEN 0.999 AND 1.001", name="normalized_vector"
        ),
        CheckConstraint("input_hash ~ '^[0-9a-f]{64}$'", name="input_hash_sha256"),
        *(
            CheckConstraint(f"{field} ~ '[^[:space:]]'", name=f"{field}_nonempty")
            for field in ("id", "revision")
        ),
    )


class EmbeddingMetadata:
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    model: Mapped[str] = mapped_column(Text, nullable=False)
    revision: Mapped[str] = mapped_column(Text, nullable=False)
    input_hash: Mapped[str] = mapped_column(Text, nullable=False)
    dimension: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=text("now()")
    )


class TextEmbedding(EmbeddingMetadata, Base):
    __tablename__ = "text_embeddings"
    __table_args__ = constraints(
        "document_id", "sentence-transformers/all-MiniLM-L6-v2", 384
    )

    document_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("documents.id", ondelete="CASCADE", onupdate="RESTRICT"),
        nullable=False,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(384), nullable=False)


class ImageEmbedding(EmbeddingMetadata, Base):
    __tablename__ = "image_embeddings"
    __table_args__ = constraints("media_id", "openai/clip-vit-base-patch32", 512)

    media_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("media.id", ondelete="CASCADE", onupdate="RESTRICT"),
        nullable=False,
    )
    embedding: Mapped[list[float]] = mapped_column(Vector(512), nullable=False)
