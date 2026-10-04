"""Session/conversation context and shared, dated culinary trend evidence."""

from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from food_recommender.infrastructure.persistence.models.base import Base
from food_recommender.infrastructure.persistence.models.mixins import Created


class BrowserSession(Created, Base):
    __tablename__ = "browser_sessions"
    __table_args__ = (
        UniqueConstraint("token_hash"),
        CheckConstraint("token_hash ~ '^[0-9a-f]{64}$'", name="token_hash_sha256"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)


class Conversation(Created, Base):
    __tablename__ = "conversations"
    __table_args__ = (
        UniqueConstraint("id", "session_id"),
        Index("ix_conversations_session", "session_id"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("browser_sessions.id", ondelete="RESTRICT"), nullable=False
    )


class Profile(Created, Base):
    __tablename__ = "profiles"
    __table_args__ = (
        CheckConstraint(
            "jsonb_typeof(preferences) = 'object'", name="preferences_object"
        ),
    )
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), primary_key=True
    )
    preferences: Mapped[dict[str, object]] = mapped_column(JSONB, nullable=False)


class DemoProfile(Base):
    __tablename__ = "demo_profiles"
    __table_args__ = (CheckConstraint("id ~ '[^[:space:]]'", name="id_nonempty"),)
    id: Mapped[str] = mapped_column(Text, primary_key=True)


class Message(Created, Base):
    __tablename__ = "messages"
    __table_args__ = (
        Index(
            "ix_messages_conversation_created", "conversation_id", "created_at", "id"
        ),
        CheckConstraint("role IN ('user', 'assistant')", name="role_values"),
        CheckConstraint(
            "content IS NOT NULL OR payload IS NOT NULL", name="content_required"
        ),
        CheckConstraint("content ~ '[^[:space:]]'", name="content_nonempty"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="payload_object"),
    )
    id: Mapped[UUID] = mapped_column(primary_key=True)
    conversation_id: Mapped[UUID] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(Text, nullable=False)
    content: Mapped[str | None] = mapped_column(Text)
    payload: Mapped[dict[str, object] | None] = mapped_column(JSONB(none_as_null=True))
    run_id: Mapped[UUID | None]


class ConversationMedia(Base):
    __tablename__ = "conversation_media"
    __table_args__ = (
        ForeignKeyConstraint(
            ["conversation_id", "session_id"],
            ["conversations.id", "conversations.session_id"],
            ondelete="CASCADE",
        ),
        ForeignKeyConstraint(
            ["media_id", "session_id"],
            ["media.id", "media.owner_session_id"],
            ondelete="RESTRICT",
        ),
        Index("ix_conversation_media_media", "media_id"),
    )
    conversation_id: Mapped[UUID] = mapped_column(primary_key=True)
    media_id: Mapped[str] = mapped_column(Text, primary_key=True)
    session_id: Mapped[UUID] = mapped_column(nullable=False)
