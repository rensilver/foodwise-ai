"""Traceable source artifacts, records, retrieval text and private catalog media.

Source rows identify file/URL content revisions, distinct from a logical
dataset. Records may remain unresolved; linked records use real catalog FKs.
Imports register mappings only, without I/O or schema creation.
"""

from datetime import date, datetime

from sqlalchemy import (
    BigInteger,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from food_recommender.infrastructure.catalog import Base


def _nonempty(*columns: str) -> tuple[CheckConstraint, ...]:
    return tuple(
        CheckConstraint(f"{column} ~ '[^[:space:]]'", name=f"{column}_nonempty")
        for column in columns
    )


def _hash(column: str) -> CheckConstraint:
    return CheckConstraint(f"{column} ~ '^[0-9a-f]{{64}}$'", name=f"{column}_sha256")


def _attribution_constraints() -> tuple[CheckConstraint, ...]:
    return (
        *_nonempty("id", "ingestion_version", "generator", "generator_revision"),
        _hash("content_hash"),
        _hash("input_hash"),
        CheckConstraint(
            "attribution IN ('source', 'imported', 'generated')",
            name="attribution_values",
        ),
        CheckConstraint(
            "attribution <> 'generated' OR (generator IS NOT NULL AND input_hash IS NOT NULL)",
            name="generation_provenance",
        ),
    )


class HashedContent:
    id: Mapped[str] = mapped_column(Text, primary_key=True)
    content_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class AttributedContent(HashedContent):
    ingestion_version: Mapped[str] = mapped_column(Text, nullable=False)
    attribution: Mapped[str] = mapped_column(Text, nullable=False)
    generator: Mapped[str | None] = mapped_column(Text)
    generator_revision: Mapped[str | None] = mapped_column(Text)
    input_hash: Mapped[str | None] = mapped_column(Text)


class Source(HashedContent, Base):
    __tablename__ = "sources"
    __table_args__ = (
        UniqueConstraint(
            "logical_source_id", "locator_kind", "locator", "content_hash"
        ),
        *_nonempty("id", "logical_source_id", "locator"),
        _hash("content_hash"),
        CheckConstraint(
            "locator_kind IN ('file', 'url', 'admin')", name="locator_kind_values"
        ),
    )

    logical_source_id: Mapped[str] = mapped_column(Text, nullable=False)
    locator_kind: Mapped[str] = mapped_column(Text, nullable=False)
    locator: Mapped[str] = mapped_column(Text, nullable=False)
    published_on: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class SourceRecord(AttributedContent, Base):
    __tablename__ = "source_records"
    __table_args__ = (
        UniqueConstraint("source_id", "record_type", "record_id"),
        *_attribution_constraints(),
        *_nonempty("record_id"),
        CheckConstraint(
            "record_type IN ('restaurant', 'recipe', 'review')",
            name="record_type_values",
        ),
        CheckConstraint(
            "raw_payload IS NOT NULL OR raw_text IS NOT NULL",
            name="raw_content_required",
        ),
        CheckConstraint(
            "num_nonnulls(restaurant_id, recipe_id, review_id) <= 1",
            name="single_entity",
        ),
        *(
            CheckConstraint(
                f"{kind}_id IS NULL OR record_type = '{kind}'", name=f"{kind}_type"
            )
            for kind in ("restaurant", "recipe", "review")
        ),
    )

    source_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("sources.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    record_type: Mapped[str] = mapped_column(Text, nullable=False)
    record_id: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[object | None] = mapped_column(JSONB(none_as_null=True))
    raw_text: Mapped[str | None] = mapped_column(Text)
    restaurant_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("restaurants.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    recipe_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("recipes.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )
    review_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("reviews.id", ondelete="RESTRICT", onupdate="RESTRICT")
    )


class Media(AttributedContent, Base):
    __tablename__ = "media"
    __table_args__ = (
        *_attribution_constraints(),
        UniqueConstraint("storage_key"),
        # Supports document/media association validation with a composite FK.
        UniqueConstraint("id", "source_record_id"),
        *_nonempty("original_locator"),
        CheckConstraint(
            "storage_key ~ '^[A-Za-z0-9][A-Za-z0-9_.-]*$'", name="storage_key_basename"
        ),
        CheckConstraint(
            "mime_type IN ('image/jpeg', 'image/png', 'image/webp')",
            name="mime_type_values",
        ),
        CheckConstraint("byte_size > 0", name="byte_size_positive"),
        CheckConstraint("width > 0 AND height > 0", name="dimensions_positive"),
    )

    source_record_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("source_records.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    storage_key: Mapped[str] = mapped_column(Text, nullable=False)
    original_locator: Mapped[str | None] = mapped_column(Text)
    mime_type: Mapped[str] = mapped_column(Text, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)


class Document(AttributedContent, Base):
    __tablename__ = "documents"
    __table_args__ = (
        *_attribution_constraints(),
        *_nonempty("kind", "text"),
        ForeignKeyConstraint(
            ["media_id", "source_record_id"],
            ["media.id", "media.source_record_id"],
            ondelete="RESTRICT",
            onupdate="RESTRICT",
        ),
        CheckConstraint(
            "(start_offset IS NULL AND end_offset IS NULL) OR "
            "(start_offset IS NOT NULL AND end_offset IS NOT NULL "
            "AND start_offset >= 0 AND end_offset > start_offset)",
            name="offset_range",
        ),
    )

    source_record_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("source_records.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    media_id: Mapped[str | None] = mapped_column(Text)
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    start_offset: Mapped[int | None] = mapped_column(Integer)
    end_offset: Mapped[int | None] = mapped_column(Integer)
