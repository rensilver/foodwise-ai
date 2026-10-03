"""context

Revision ID: 0005_context
Revises: 0004_search
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_context"
down_revision: str | Sequence[str] | None = "0004_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "browser_sessions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "token_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_browser_sessions_token_hash_sha256"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_browser_sessions")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_browser_sessions_token_hash")),
    )
    op.create_table(
        "demo_profiles",
        sa.Column("id", sa.Text(), nullable=False),
        sa.CheckConstraint(
            "id ~ '[^[:space:]]'", name=op.f("ck_demo_profiles_id_nonempty")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_demo_profiles")),
    )
    op.create_table(
        "trend_cache",
        sa.Column("query_hash", sa.Text(), nullable=False),
        sa.Column("query", sa.Text(), nullable=False),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "expires_at > retrieved_at AND expires_at <= retrieved_at + interval '24 hours'",
            name=op.f("ck_trend_cache_cache_lifetime"),
        ),
        sa.CheckConstraint(
            "query ~ '[^[:space:]]'", name=op.f("ck_trend_cache_query_nonempty")
        ),
        sa.CheckConstraint(
            "query_hash ~ '^[0-9a-f]{64}$'",
            name=op.f("ck_trend_cache_query_hash_sha256"),
        ),
        sa.PrimaryKeyConstraint("query_hash", name=op.f("pk_trend_cache")),
    )
    op.create_index(
        "ix_trend_cache_expiry", "trend_cache", ["expires_at"], unique=False
    )
    op.create_table(
        "conversations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["browser_sessions.id"],
            name=op.f("fk_conversations_session_id_browser_sessions"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_conversations")),
        sa.UniqueConstraint("id", "session_id", name=op.f("uq_conversations_id")),
    )
    op.create_index(
        "ix_conversations_session", "conversations", ["session_id"], unique=False
    )
    op.create_table(
        "trend_evidence",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("query_hash", sa.Text(), nullable=False),
        sa.Column("position", sa.Integer(), nullable=False),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=False),
        sa.Column("published_on", sa.Date(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "excerpt ~ '[^[:space:]]'", name=op.f("ck_trend_evidence_excerpt_nonempty")
        ),
        sa.CheckConstraint(
            "url ~ '^https?://[^[:space:]]+$'", name=op.f("ck_trend_evidence_url_http")
        ),
        sa.CheckConstraint(
            "position BETWEEN 0 AND 4", name=op.f("ck_trend_evidence_position_range")
        ),
        sa.ForeignKeyConstraint(
            ["query_hash"],
            ["trend_cache.query_hash"],
            name=op.f("fk_trend_evidence_query_hash_trend_cache"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_trend_evidence")),
        sa.UniqueConstraint(
            "query_hash", "position", name=op.f("uq_trend_evidence_query_hash")
        ),
    )
    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.Text(), nullable=False),
        sa.Column("content", sa.Text(), nullable=True),
        sa.Column(
            "payload",
            postgresql.JSONB(none_as_null=True, astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("run_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "content ~ '[^[:space:]]'", name=op.f("ck_messages_content_nonempty")
        ),
        sa.CheckConstraint(
            "jsonb_typeof(payload) = 'object'", name=op.f("ck_messages_payload_object")
        ),
        sa.CheckConstraint(
            "role IN ('user', 'assistant')", name=op.f("ck_messages_role_values")
        ),
        sa.CheckConstraint(
            "content IS NOT NULL OR payload IS NOT NULL",
            name=op.f("ck_messages_content_required"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_messages_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_messages")),
    )
    op.create_index(
        "ix_messages_conversation_created",
        "messages",
        ["conversation_id", "created_at", "id"],
        unique=False,
    )
    op.create_table(
        "profiles",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column(
            "preferences", postgresql.JSONB(astext_type=sa.Text()), nullable=False
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "jsonb_typeof(preferences) = 'object'",
            name=op.f("ck_profiles_preferences_object"),
        ),
        sa.ForeignKeyConstraint(
            ["conversation_id"],
            ["conversations.id"],
            name=op.f("fk_profiles_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("conversation_id", name=op.f("pk_profiles")),
    )
    op.add_column("media", sa.Column("owner_session_id", sa.Uuid(), nullable=True))
    op.alter_column("media", "source_record_id", existing_type=sa.TEXT(), nullable=True)
    op.create_foreign_key(
        op.f("fk_media_owner_session_id_browser_sessions"),
        "media",
        "browser_sessions",
        ["owner_session_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_unique_constraint(
        "uq_media_owner_identity", "media", ["id", "owner_session_id"]
    )
    op.create_table(
        "conversation_media",
        sa.Column("conversation_id", sa.Uuid(), nullable=False),
        sa.Column("media_id", sa.Text(), nullable=False),
        sa.Column("session_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(
            ["conversation_id", "session_id"],
            ["conversations.id", "conversations.session_id"],
            name=op.f("fk_conversation_media_conversation_id_conversations"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["media_id", "session_id"],
            ["media.id", "media.owner_session_id"],
            name=op.f("fk_conversation_media_media_id_media"),
            ondelete="RESTRICT",
        ),
        sa.PrimaryKeyConstraint(
            "conversation_id", "media_id", name=op.f("pk_conversation_media")
        ),
    )
    op.create_index(
        "ix_conversation_media_media", "conversation_media", ["media_id"], unique=False
    )
    op.execute(
        "INSERT INTO demo_profiles (id) SELECT DISTINCT demo_profile_id FROM reviews"
    )
    op.create_foreign_key(
        op.f("fk_reviews_demo_profile_id_demo_profiles"),
        "reviews",
        "demo_profiles",
        ["demo_profile_id"],
        ["id"],
        ondelete="RESTRICT",
    )

    op.create_check_constraint(
        op.f("ck_media_media_ownership"),
        "media",
        "num_nonnulls(source_record_id, owner_session_id) = 1",
    )


def downgrade() -> None:
    op.drop_index("ix_conversation_media_media", table_name="conversation_media")
    op.drop_table("conversation_media")
    op.drop_constraint("uq_media_owner_identity", "media", type_="unique")
    op.drop_constraint(op.f("ck_media_media_ownership"), "media", type_="check")
    op.drop_constraint(
        op.f("fk_reviews_demo_profile_id_demo_profiles"), "reviews", type_="foreignkey"
    )
    op.drop_constraint(
        op.f("fk_media_owner_session_id_browser_sessions"), "media", type_="foreignkey"
    )
    op.alter_column(
        "media", "source_record_id", existing_type=sa.TEXT(), nullable=False
    )
    op.drop_column("media", "owner_session_id")
    op.drop_table("profiles")
    op.drop_index("ix_messages_conversation_created", table_name="messages")
    op.drop_table("messages")
    op.drop_table("trend_evidence")
    op.drop_index("ix_conversations_session", table_name="conversations")
    op.drop_table("conversations")
    op.drop_index("ix_trend_cache_expiry", table_name="trend_cache")
    op.drop_table("trend_cache")
    op.drop_table("demo_profiles")
    op.drop_table("browser_sessions")
