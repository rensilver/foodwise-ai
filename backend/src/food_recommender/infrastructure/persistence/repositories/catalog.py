"""Catalog persistence and atomic source, document, media and vector writes."""

from dataclasses import asdict, fields
from typing import Any, cast

from sqlalchemy import Select, delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as upsert
from sqlalchemy.ext.asyncio import AsyncSession

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.domain.catalog import (
    CatalogSnapshot,
    PreparedCatalog,
    RecipeData,
    RestaurantData,
)
from food_recommender.domain.evidence import Citation, CitationKind
from food_recommender.domain.values import Category, EntityRef
from food_recommender.infrastructure.persistence.models.catalog import (
    Recipe,
    Restaurant,
    Review,
)
from food_recommender.infrastructure.persistence.models.cleanup import MediaCleanupJob
from food_recommender.infrastructure.persistence.models.embeddings import (
    ImageEmbedding,
    TextEmbedding,
)
from food_recommender.infrastructure.persistence.models.provenance import (
    Document,
    Media,
    Source,
    SourceRecord,
)


def model_for(ref: EntityRef) -> type[Restaurant] | type[Recipe]:
    if ref.category == Category.RESTAURANT:
        return Restaurant
    if ref.category == Category.RECIPE:
        return Recipe
    raise ApplicationError(ErrorCode.INVALID_REQUEST)


def snapshot(row: Restaurant | Recipe) -> CatalogSnapshot:
    data_type = RestaurantData if isinstance(row, Restaurant) else RecipeData
    values = {field.name: getattr(row, field.name) for field in fields(data_type)}
    for key in ("ingredients", "directions", "signatures", "shortcomings", "allergens"):
        if values.get(key) is not None:
            values[key] = tuple(values[key])
    return CatalogSnapshot(data_type(**values), row.version)


class PostgresCatalogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def browse(
        self, category: Category, filters: dict[str, object]
    ) -> tuple[tuple[CatalogSnapshot, ...], int]:
        model = model_for(EntityRef(category, "browse"))
        conditions = []
        for key in ("cuisine", "location"):
            value = filters.get(key)
            if value is not None:
                conditions.append(
                    getattr(model, "normalized_" + key) == str(value).strip().casefold()
                )
        if filters.get("price_band") is not None:
            conditions.append(Restaurant.price_band <= filters["price_band"])
        if filters.get("q"):
            query = (
                str(filters["q"])
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            conditions.append(model.name.ilike("%" + query + "%", escape="\\"))
        total = await self.session.scalar(
            select(func.count()).select_from(model).where(*conditions)
        )
        rows = (
            await self.session.scalars(
                select(model)
                .where(*conditions)
                .order_by(model.id)
                .limit(cast(int, filters["limit"]))
                .offset(cast(int, filters["offset"]))
            )
        ).all()
        return tuple(
            snapshot(cast(Restaurant | Recipe, row)) for row in rows
        ), total or 0

    async def citations(self, ref: EntityRef) -> tuple[Citation, ...]:
        link = (
            SourceRecord.restaurant_id
            if ref.category == Category.RESTAURANT
            else SourceRecord.recipe_id
        )
        rows = (
            await self.session.execute(
                select(Document, SourceRecord, Source)
                .join(SourceRecord, Document.source_record_id == SourceRecord.id)
                .join(Source, SourceRecord.source_id == Source.id)
                .where(link == ref.id)
                .order_by(Document.id)
                .limit(20)
            )
        ).all()
        return tuple(
            Citation(
                id=document.id,
                kind=CitationKind.CATALOG,
                source_id=source.id,
                excerpt=document.text[:1500],
                entity=ref,
                record_id=record.record_id,
                document_id=document.id,
                published_on=source.published_on,
                retrieved_at=source.retrieved_at,
                attribution=cast(Any, document.attribution),
            )
            for document, record, source in rows
        )

    async def get(self, ref: EntityRef) -> CatalogSnapshot:
        row = await self.session.get(model_for(ref), ref.id, populate_existing=True)
        if row is None:
            raise ApplicationError(ErrorCode.NOT_FOUND)
        return snapshot(cast(Restaurant | Recipe, row))

    async def create(self, prepared: PreparedCatalog) -> CatalogSnapshot:
        model = Restaurant if isinstance(prepared.data, RestaurantData) else Recipe
        await self.session.execute(insert(model).values(**asdict(prepared.data)))
        await self._write_content(prepared)
        ref = EntityRef(
            Category.RESTAURANT if model is Restaurant else Category.RECIPE,
            prepared.data.id,
        )
        return await self.get(ref)

    def _validate(
        self,
        ref: EntityRef,
        expected_version: int,
        prepared: PreparedCatalog | None = None,
    ) -> None:
        if type(expected_version) is not int or expected_version < 1:
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        if prepared is not None and (
            ref.id != prepared.data.id
            or (ref.category == Category.RESTAURANT)
            != isinstance(prepared.data, RestaurantData)
        ):
            raise ApplicationError(ErrorCode.INVALID_REQUEST)

    async def _remove_content(
        self, ref: EntityRef, *, preserve_media: bool = False
    ) -> tuple[str, ...]:
        link = (
            SourceRecord.restaurant_id
            if ref.category == Category.RESTAURANT
            else SourceRecord.recipe_id
        )
        return await self._remove_records(
            select(SourceRecord.id).where(link == ref.id), preserve_media=preserve_media
        )

    async def _remove_records(
        self, record_ids: Select[str], *, preserve_media: bool = False
    ) -> tuple[str, ...]:
        await self.session.execute(
            delete(Document).where(
                Document.source_record_id.in_(record_ids),
                *([Document.media_id.is_(None)] if preserve_media else []),
            )
        )
        if preserve_media:
            return ()
        keys = tuple(
            (
                await self.session.execute(
                    delete(Media)
                    .where(Media.source_record_id.in_(record_ids))
                    .returning(Media.storage_key)
                )
            ).scalars()
        )
        for key in keys:
            await self.session.execute(
                upsert(MediaCleanupJob).values(storage_key=key).on_conflict_do_nothing()
            )
        return keys

    async def replace(
        self, ref: EntityRef, prepared: PreparedCatalog, expected_version: int
    ) -> CatalogSnapshot:
        self._validate(ref, expected_version, prepared)
        current = await self.get(ref)
        if (current.data.source_id, current.data.source_record_id) != (
            prepared.data.source_id,
            prepared.data.source_record_id,
        ):
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        model = model_for(ref)
        values = asdict(prepared.data)
        for key in ("id", "source_id", "source_record_id"):
            values.pop(key)
        changed = await self.session.scalar(
            update(model)
            .where(model.id == ref.id, model.version == expected_version)
            .values(**values, version=model.version + 1)
            .returning(model.id)
        )
        if changed is None:
            raise ApplicationError(ErrorCode.CONFLICT)
        # Remove old retrieval rows; source/raw revisions survive as provenance.
        await self._remove_content(ref, preserve_media=prepared.preserve_media)
        await self._write_content(prepared)
        return await self.get(ref)

    async def delete(
        self, ref: EntityRef, expected_version: int, *, include_reviews: bool = False
    ) -> tuple[str, ...]:
        self._validate(ref, expected_version)
        model = model_for(ref)
        # Lock by updating the version before removing linked retrieval content.
        changed = await self.session.scalar(
            update(model)
            .where(model.id == ref.id, model.version == expected_version)
            .values(version=model.version + 1)
            .returning(model.id)
        )
        if changed is None:
            await self.get(ref)
            raise ApplicationError(ErrorCode.CONFLICT)
        keys = await self._remove_content(ref)
        if ref.category == Category.RESTAURANT and include_reviews:
            reviews = select(Review.id).where(Review.restaurant_id == ref.id)
            keys += await self._remove_records(
                select(SourceRecord.id).where(SourceRecord.review_id.in_(reviews))
            )
            await self.session.execute(
                update(SourceRecord)
                .where(SourceRecord.review_id.in_(reviews))
                .values(review_id=None)
            )
            await self.session.execute(
                delete(Review).where(Review.restaurant_id == ref.id)
            )
        link = (
            SourceRecord.restaurant_id
            if ref.category == Category.RESTAURANT
            else SourceRecord.recipe_id
        )
        await self.session.execute(
            update(SourceRecord).where(link == ref.id).values({link.key: None})
        )
        await self.session.execute(delete(model).where(model.id == ref.id))
        return keys

    async def _ensure(
        self, model: type[Source] | type[SourceRecord], payload: dict[str, Any]
    ) -> None:
        # Reusing an immutable provenance ID requires exactly the same values.
        existing = await self.session.get(model, payload["id"])
        if existing is None:
            await self.session.execute(insert(model).values(**payload))
        elif any(getattr(existing, key) != value for key, value in payload.items()):
            raise ApplicationError(ErrorCode.CONFLICT)

    async def _write_content(self, prepared: PreparedCatalog) -> None:
        for source in prepared.sources:
            await self._ensure(Source, asdict(source))
        category = (
            "restaurant" if isinstance(prepared.data, RestaurantData) else "recipe"
        )
        for record in prepared.records:
            await self._ensure(
                SourceRecord, {**asdict(record), f"{category}_id": prepared.data.id}
            )
        for media in prepared.media:
            await self.session.execute(insert(Media).values(**asdict(media)))
        for document in prepared.documents:
            await self.session.execute(insert(Document).values(**asdict(document)))
        for vectors, model, parent in (
            (prepared.text_embeddings, TextEmbedding, "document_id"),
            (prepared.image_embeddings, ImageEmbedding, "media_id"),
        ):
            for vector in vectors:
                await self.session.execute(
                    insert(model).values(
                        id=vector.id,
                        **{parent: vector.parent_id},
                        model=vector.model,
                        revision=vector.revision,
                        input_hash=vector.input_hash,
                        dimension=len(vector.values),
                        embedding=list(vector.values),
                    )
                )
