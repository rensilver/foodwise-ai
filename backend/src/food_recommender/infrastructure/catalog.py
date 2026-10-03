"""SQLAlchemy catalog mappings; imports never create engines or connect.

IDs are explicit, opaque strings preserving legacy IDs in separate table
namespaces. A logical source ID denotes a dataset, not an enrichment filename.
Unknown metadata has no fabricated defaults, including ingredient/allergen lists.
"""

from datetime import date

from sqlalchemy import (
    CheckConstraint,
    Date,
    Float,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    metadata = MetaData(
        naming_convention={
            "pk": "pk_%(table_name)s",
            "uq": "uq_%(table_name)s_%(column_0_name)s",
            "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
            "ck": "ck_%(table_name)s_%(constraint_name)s",
        }
    )


class SourceIdentity:
    """Caller-assigned identity and a unique source/type/record reference."""

    id: Mapped[str] = mapped_column(Text, primary_key=True)
    source_id: Mapped[str] = mapped_column(Text, nullable=False)
    source_record_id: Mapped[str] = mapped_column(Text, nullable=False)
    version: Mapped[int] = mapped_column(
        Integer, server_default=text("1"), nullable=False
    )


def _identity_constraints() -> tuple[UniqueConstraint | CheckConstraint, ...]:
    # The table supplies the entity type component of source/type/record identity.
    return (
        UniqueConstraint("source_id", "source_record_id"),
        CheckConstraint("version > 0", name="version_positive"),
        *(
            CheckConstraint(f"{column} ~ '[^[:space:]]'", name=f"{column}_nonempty")
            for column in ("id", "source_id", "source_record_id")
        ),
    )


class Restaurant(SourceIdentity, Base):
    __tablename__ = "restaurants"
    __table_args__ = (
        Index(
            "ix_restaurants_filters",
            "normalized_cuisine",
            "normalized_location",
            "price_band",
        ),
        Index("ix_restaurants_location_price", "normalized_location", "price_band"),
        *_identity_constraints(),
        CheckConstraint("name ~ '[^[:space:]]'", name="name_nonempty"),
        CheckConstraint("price_band BETWEEN 1 AND 4", name="price_band_range"),
        CheckConstraint("rating BETWEEN 0 AND 5", name="rating_range"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="latitude_range"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="longitude_range"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    cuisine: Mapped[str | None] = mapped_column(Text)
    normalized_cuisine: Mapped[str | None] = mapped_column(Text)
    location: Mapped[str | None] = mapped_column(Text)
    normalized_location: Mapped[str | None] = mapped_column(Text)
    restaurant_type: Mapped[str | None] = mapped_column(Text)
    rating: Mapped[float | None] = mapped_column(Float)
    price_band: Mapped[int | None] = mapped_column(Integer)
    signatures: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    vibe: Mapped[str | None] = mapped_column(Text)
    environment: Mapped[str | None] = mapped_column(Text)
    shortcomings: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    availability: Mapped[str | None] = mapped_column(Text)
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    allergens: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class Recipe(SourceIdentity, Base):
    __tablename__ = "recipes"
    __table_args__ = (
        Index("ix_recipes_cuisine", "normalized_cuisine"),
        *_identity_constraints(),
        CheckConstraint("name ~ '[^[:space:]]'", name="name_nonempty"),
        CheckConstraint("servings > 0", name="servings_positive"),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    cuisine: Mapped[str | None] = mapped_column(Text)
    normalized_cuisine: Mapped[str | None] = mapped_column(Text)
    servings: Mapped[int | None] = mapped_column(Integer)
    prep_time: Mapped[str | None] = mapped_column(Text)
    cook_time: Mapped[str | None] = mapped_column(Text)
    total_time: Mapped[str | None] = mapped_column(Text)
    ingredients: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    directions: Mapped[list[str] | None] = mapped_column(ARRAY(Text))
    difficulty: Mapped[str | None] = mapped_column(Text)
    nutrition: Mapped[dict[str, object] | None] = mapped_column(
        JSONB(none_as_null=True)
    )
    availability: Mapped[str | None] = mapped_column(Text)
    allergens: Mapped[list[str] | None] = mapped_column(ARRAY(Text))


class Review(SourceIdentity, Base):
    __tablename__ = "reviews"
    __table_args__ = (
        Index("ix_reviews_profile_restaurant", "demo_profile_id", "restaurant_id"),
        *_identity_constraints(),
        CheckConstraint(
            "demo_profile_id ~ '[^[:space:]]'", name="demo_profile_id_nonempty"
        ),
        CheckConstraint("text ~ '[^[:space:]]'", name="text_nonempty"),
        CheckConstraint("rating BETWEEN 0 AND 5", name="rating_range"),
    )

    restaurant_id: Mapped[str] = mapped_column(
        Text,
        ForeignKey("restaurants.id", ondelete="RESTRICT", onupdate="RESTRICT"),
        nullable=False,
    )
    demo_profile_id: Mapped[str] = mapped_column(
        Text, ForeignKey("demo_profiles.id", ondelete="RESTRICT"), nullable=False
    )
    title: Mapped[str | None] = mapped_column(Text)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    rating: Mapped[float | None] = mapped_column(Float)
    published_on: Mapped[date | None] = mapped_column(Date)
    language: Mapped[str | None] = mapped_column(Text)
