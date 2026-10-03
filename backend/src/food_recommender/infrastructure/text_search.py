"""Parameterized FTS and exact cosine branches with identical source filters."""

from typing import Literal, cast

from sqlalchemy import ColumnElement, and_, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from food_recommender.domain.evidence import Citation, CitationKind
from food_recommender.domain.values import Category, EntityRef
from food_recommender.infrastructure.catalog import Recipe, Restaurant, Review
from food_recommender.infrastructure.embeddings import TextEmbedding
from food_recommender.infrastructure.provenance import Document, Source, SourceRecord
from food_recommender.infrastructure.text_encoder import (
    MINILM_MODEL,
    MINILM_REVISION,
    validate_query,
)
from food_recommender.retrieval.models import TextHit, TextPlan


def normalize(value: str) -> str:
    return " ".join(value.casefold().split())


class PostgresTextSearch:
    def __init__(self, sessions: async_sessionmaker[AsyncSession]) -> None:
        self.sessions = sessions

    async def search(
        self,
        plan: TextPlan,
        category: Category,
        branch: Literal["lexical", "dense"],
        vector: tuple[float, ...] | None = None,
        *,
        model: str = MINILM_MODEL,
        revision: str = MINILM_REVISION,
    ) -> tuple[TextHit, ...]:
        if category not in plan.categories or branch not in ("lexical", "dense"):
            raise ValueError("Invalid category/branch")
        if branch == "dense":
            if vector is None:
                raise ValueError("Dense query requires a vector")
            validate_query(vector, model, revision)
        entity = Restaurant if category == Category.RESTAURANT else Recipe
        entity_link = (
            SourceRecord.restaurant_id
            if category == Category.RESTAURANT
            else SourceRecord.recipe_id
        )
        query = func.plainto_tsquery("english", plan.query)
        score = (
            func.ts_rank_cd(Document.search_vector, query)
            if branch == "lexical"
            else 1 - TextEmbedding.embedding.cosine_distance(list(vector or ()))
        )
        statement = (
            select(Document, SourceRecord, Source, entity, score.label("score"))
            .select_from(Document)
            .join(SourceRecord, SourceRecord.id == Document.source_record_id)
            .join(Source, Source.id == SourceRecord.source_id)
        )
        if category == Category.RESTAURANT:
            statement = statement.outerjoin(
                Review, Review.id == SourceRecord.review_id
            ).join(
                Restaurant,
                Restaurant.id == func.coalesce(entity_link, Review.restaurant_id),
            )
            source_conditions: list[ColumnElement[bool]] = []
            if "restaurant" in plan.sources:
                source_conditions.append(SourceRecord.restaurant_id.is_not(None))
            if "review" in plan.sources:
                source_conditions.append(
                    and_(
                        SourceRecord.review_id.is_not(None),
                        Review.demo_profile_id == plan.demo_profile_id,
                    )
                )
            statement = statement.where(
                or_(*source_conditions) if source_conditions else false()
            )
            if plan.location is not None:
                statement = statement.where(
                    Restaurant.normalized_location == normalize(plan.location)
                )
            if plan.max_price_band is not None:
                statement = statement.where(
                    Restaurant.price_band <= plan.max_price_band
                )
        else:
            statement = statement.join(Recipe, Recipe.id == entity_link).where(
                true() if "recipe" in plan.sources else false()
            )
        if plan.cuisine is not None:
            statement = statement.where(
                entity.normalized_cuisine == normalize(plan.cuisine)
            )
        if plan.name is not None:
            statement = statement.where(func.lower(entity.name) == normalize(plan.name))
        if plan.entity_ids:
            statement = statement.where(entity.id.in_(plan.entity_ids))
        # Search only bounded encoder projections, never oversized original captions.
        statement = statement.where(Document.kind.like("retrieval_%"))
        if branch == "lexical":
            statement = statement.where(Document.search_vector.bool_op("@@")(query))
        else:
            statement = statement.join(
                TextEmbedding, TextEmbedding.document_id == Document.id
            ).where(
                TextEmbedding.model == model,
                TextEmbedding.revision == revision,
                TextEmbedding.dimension == 384,
                TextEmbedding.input_hash == Document.content_hash,
            )
        # Rank entities before limiting: duplicate chunks cannot crowd out peers.
        # Exhaustive document search is intentional for this small exact-search corpus.
        statement = statement.order_by(score.desc(), entity.id, Document.id)
        async with self.sessions() as session:
            rows = (await session.execute(statement)).all()
        hits = []
        for doc, record, source, item, original_score in rows:
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
                TextHit(
                    ref,
                    item.name,
                    citation,
                    float(original_score) if branch == "lexical" else None,
                    float(original_score) if branch == "dense" else None,
                    tuple(item.ingredients)
                    if isinstance(item, Recipe) and item.ingredients is not None
                    else None,
                    tuple(item.allergens) if item.allergens is not None else None,
                    cast(Literal["restaurant", "recipe", "review"], record.record_type),
                )
            )
        return tuple(hits)
