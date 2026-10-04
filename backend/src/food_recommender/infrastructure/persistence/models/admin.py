"""Revocable local admin authority, separate from browser conversation ownership."""

from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column

from food_recommender.infrastructure.persistence.models.base import Base


class AdminSession(Base):
    __tablename__ = "admin_sessions"
    __table_args__ = (
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="token_hash_sha256"),
        CheckConstraint("csrf_hash ~ '^[0-9a-f]{64}$'", name="csrf_hash_sha256"),
    )
    token_hash: Mapped[str] = mapped_column(Text, primary_key=True)
    csrf_hash: Mapped[str] = mapped_column(Text, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
