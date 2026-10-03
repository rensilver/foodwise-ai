"""Durable cleanup outbox; jobs are committed before removing any files."""

from sqlalchemy import CheckConstraint, Text
from sqlalchemy.orm import Mapped, mapped_column

from food_recommender.infrastructure.context import Base as Base
from food_recommender.infrastructure.context import Created


class MediaCleanupJob(Created, Base):
    __tablename__ = "media_cleanup_jobs"
    __table_args__ = (
        CheckConstraint(
            "storage_key ~ '^[A-Za-z0-9][A-Za-z0-9_.-]*$'", name="storage_key_basename"
        ),
    )
    storage_key: Mapped[str] = mapped_column(Text, primary_key=True)
