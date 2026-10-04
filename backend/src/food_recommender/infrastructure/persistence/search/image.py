"""Exact CLIP cosine search, real media links and parameterized shared filters."""

from typing import Any, cast

from sqlalchemy import ColumnElement, and_, false, func, or_, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.sql import Select

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.domain.evidence import Citation, CitationKind
from food_recommender.domain.values import Category, EntityRef
from food_recommender.infrastructure.persistence.models.catalog import (
    Recipe,
    Restaurant,
    Review,
)
from food_recommender.infrastructure.persistence.models.embeddings import ImageEmbedding
from food_recommender.infrastructure.persistence.models.provenance import (
    Document,
    Media,
    Source,
    SourceRecord,
)
from food_recommender.infrastructure.persistence.search.filters import metadata_filters
from food_recommender.retrieval.dietary import assess, eligible
from food_recommender.retrieval.embedding_contracts import validate_clip
from food_recommender.retrieval.models import ImageHit, TextPlan


class PostgresImageSearch:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def search(
        self,
        plan: TextPlan,
        category: Category,
        vector: tuple[float, ...],
        *,
        model: str,
        revision: str,
    ) -> tuple[ImageHit, ...]:
        validate_clip(vector, model, revision)
        if category not in plan.categories:
            raise ValueError("Unrequested category")
        try:
            return await self._search(
                plan, category, vector, model=model, revision=revision
            )
        except SQLAlchemyError:
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE) from None

    async def _search(
        self,
        plan: TextPlan,
        category: Category,
        vector: tuple[float, ...],
        *,
        model: str,
        revision: str,
    ) -> tuple[ImageHit, ...]:
        entity = Recipe if category == Category.RECIPE else Restaurant
        statement = cast(
            Select[Any],
            (
                select(Media, SourceRecord, Source, entity)
                .join(SourceRecord, SourceRecord.id == Media.source_record_id)
                .join(Source, Source.id == SourceRecord.source_id)
            ),
        )
        if category == Category.RECIPE:
            statement = statement.join(Recipe, Recipe.id == SourceRecord.recipe_id)
            if "recipe" not in plan.sources:
                statement = statement.where(false())
        else:
            statement = statement.outerjoin(
                Review, Review.id == SourceRecord.review_id
            ).join(
                Restaurant,
                Restaurant.id
                == func.coalesce(SourceRecord.restaurant_id, Review.restaurant_id),
            )
            conditions: list[ColumnElement[bool]] = []
            if "restaurant" in plan.sources:
                conditions.append(SourceRecord.restaurant_id.is_not(None))
            if "review" in plan.sources:
                conditions.append(
                    and_(
                        SourceRecord.review_id.is_not(None),
                        Review.demo_profile_id == plan.demo_profile_id,
                    )
                )
            statement = statement.where(or_(*conditions) if conditions else false())
        statement = metadata_filters(statement, plan, category)
        score = 1 - ImageEmbedding.embedding.cosine_distance(list(vector))
        async with self.sessions() as session:
            expected = set(
                (await session.scalars(statement.with_only_columns(Media.id))).all()
            )
            ranked = (
                statement.add_columns(Document, score.label("score"))
                .join(ImageEmbedding, ImageEmbedding.media_id == Media.id)
                .join(
                    Document,
                    and_(
                        Document.media_id == Media.id,
                        Document.source_record_id == Media.source_record_id,
                        Document.kind == "image_association",
                    ),
                )
                .where(
                    ImageEmbedding.model == model,
                    ImageEmbedding.revision == revision,
                    ImageEmbedding.dimension == 512,
                    ImageEmbedding.input_hash == Media.content_hash,
                )
                .order_by(score.desc(), entity.id, Media.id)
            )
            rows = (await session.execute(ranked)).all()
        if expected != {row[0].id for row in rows}:
            raise ApplicationError(ErrorCode.DEPENDENCY_UNAVAILABLE)
        hits = []
        for media, record, source, item, doc, similarity in rows:
            ingredients = (
                tuple(item.ingredients)
                if isinstance(item, Recipe) and item.ingredients is not None
                else None
            )
            allergens = tuple(item.allergens) if item.allergens is not None else None
            if not eligible(
                tuple(assess(c, ingredients, allergens) for c in plan.constraints)
            ):
                continue
            ref = EntityRef(category, item.id)
            citation = Citation(
                id=doc.id,
                kind=CitationKind.CATALOG,
                source_id=source.id,
                excerpt=doc.text,
                entity=ref,
                record_id=record.record_id,
                document_id=doc.id,
                published_on=source.published_on,
                retrieved_at=source.retrieved_at,
                attribution=doc.attribution,
            )
            hits.append(
                ImageHit(
                    ref,
                    item.name,
                    citation,
                    media.id,
                    float(similarity),
                    ingredients,
                    allergens,
                )
            )
        # Exhaustive exact retrieval: aggregate before applying entity limits/fusion.
        return tuple(hits)
