"""Dated trend cache and evidence mappings."""

from datetime import date, datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from food_recommender.infrastructure.persistence.models.base import Base


class TrendCache(Base):
    __tablename__ = "trend_cache"
    __table_args__ = (
        CheckConstraint("query_hash ~ '^[0-9a-f]{64}$'", name="query_hash_sha256"),
        CheckConstraint("query ~ '[^[:space:]]'", name="query_nonempty"),
        CheckConstraint(
            "expires_at > retrieved_at AND expires_at <= retrieved_at + interval '24 hours'",
            name="cache_lifetime",
        ),
        Index("ix_trend_cache_expiry", "expires_at"),
    )
    query_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    query: Mapped[str] = mapped_column(Text, nullable=False)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )


class TrendEvidence(Base):
    __tablename__ = "trend_evidence"
    __table_args__ = (
        UniqueConstraint("query_hash", "position"),
        CheckConstraint("position BETWEEN 0 AND 4", name="position_range"),
        CheckConstraint("url ~ '^https?://[^[:space:]]+$'", name="url_http"),
        CheckConstraint("excerpt ~ '[^[:space:]]'", name="excerpt_nonempty"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    query_hash: Mapped[str] = mapped_column(
        Text, ForeignKey("trend_cache.query_hash", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    published_on: Mapped[date | None] = mapped_column(Date)
    retrieved_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
