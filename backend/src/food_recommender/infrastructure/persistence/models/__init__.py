"""Register all ORM tables once, without engines, connections or provider imports."""

from food_recommender.infrastructure.persistence.models import (
    admin,
    catalog,
    cleanup,
    context,
    embeddings,
    ingestion,
    provenance,
    trends,
)
from food_recommender.infrastructure.persistence.models.base import Base

__all__ = [
    "Base",
    "admin",
    "catalog",
    "cleanup",
    "context",
    "embeddings",
    "ingestion",
    "provenance",
    "trends",
]
