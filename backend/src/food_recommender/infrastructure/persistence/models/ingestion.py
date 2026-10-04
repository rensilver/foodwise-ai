"""Hash and version checkpoints for idempotent catalog ingestion."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Integer, Text, text
from sqlalchemy.orm import Mapped, mapped_column

from food_recommender.infrastructure.persistence.models.base import Base


class IngestionCheckpoint(Base):
    __tablename__ = "ingestion_checkpoints"
    __table_args__ = (
        CheckConstraint(
            "category IN ('restaurant', 'recipe', 'review')", name="category_values"
        ),
        CheckConstraint("entity_id ~ '[^[:space:]]'", name="entity_id_nonempty"),
        CheckConstraint("fingerprint ~ '^[0-9a-f]{64}$'", name="fingerprint_sha256"),
        CheckConstraint("catalog_version > 0", name="version_positive"),
    )
    category: Mapped[str] = mapped_column(Text, primary_key=True)
    entity_id: Mapped[str] = mapped_column(Text, primary_key=True)
    fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    ingestion_version: Mapped[str] = mapped_column(Text, nullable=False)
    catalog_version: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=text("now()"), nullable=False
    )
