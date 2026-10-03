"""Conversation ownership, persistence and supported checkpoint setup."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError

from food_recommender.infrastructure.checkpoints import (
    checkpoint_saver,
    setup_checkpoints,
)
from food_recommender.infrastructure.context import (
    BrowserSession,
    Conversation,
    ConversationMedia,
    Message,
    Profile,
    TrendCache,
    TrendEvidence,
)
from food_recommender.infrastructure.provenance import Media


@pytest.fixture
def context(catalog):
    connection, _ = catalog
    session_id, other_session, conversation_id = uuid4(), uuid4(), uuid4()
    connection.execute(
        insert(BrowserSession),
        [
            dict(id=session_id, token_hash="a" * 64),
            dict(id=other_session, token_hash="b" * 64),
        ],
    )
    connection.execute(
        insert(Conversation), dict(id=conversation_id, session_id=session_id)
    )
    return connection, session_id, other_session, conversation_id


def test_context_roundtrip_and_unknown_trend_dates(context):
    connection, session_id, _, conversation_id = context
    connection.execute(
        insert(Profile),
        dict(conversation_id=conversation_id, preferences={"constraints": []}),
    )
    connection.execute(
        insert(Message),
        dict(
            id=uuid4(), conversation_id=conversation_id, role="user", content="Dinner"
        ),
    )
    now = datetime(2026, 10, 3, tzinfo=UTC)
    connection.execute(
        insert(TrendCache),
        dict(
            query_hash="c" * 64,
            query="mushroom cuisine",
            retrieved_at=now,
            expires_at=now + timedelta(hours=24),
        ),
    )
    connection.execute(
        insert(TrendEvidence),
        dict(
            id=uuid4(),
            query_hash="c" * 64,
            position=0,
            url="https://example.test/article",
            excerpt="Evidence",
            retrieved_at=now,
        ),
    )
    assert (
        connection.execute(select(Conversation.session_id)).scalar_one() == session_id
    )
    assert connection.execute(select(Profile.preferences)).scalar_one() == {
        "constraints": []
    }
    assert connection.execute(select(TrendEvidence.published_on)).scalar_one() is None
    assert connection.execute(select(Message.content)).scalar_one() == "Dinner"


def test_upload_association_requires_matching_session(context):
    connection, session_id, other_session, conversation_id = context
    upload = dict(
        id="upload",
        owner_session_id=other_session,
        source_record_id=None,
        storage_key="upload.png",
        mime_type="image/png",
        byte_size=10,
        width=2,
        height=2,
        content_hash="a" * 64,
        ingestion_version="upload-v1",
        attribution="source",
    )
    connection.execute(insert(Media), upload)
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(
                insert(ConversationMedia),
                dict(
                    conversation_id=conversation_id,
                    session_id=session_id,
                    media_id="upload",
                ),
            )
    other_conversation = uuid4()
    connection.execute(
        insert(Conversation), dict(id=other_conversation, session_id=other_session)
    )
    connection.execute(
        insert(ConversationMedia),
        dict(
            conversation_id=other_conversation,
            session_id=other_session,
            media_id="upload",
        ),
    )
    assert (
        connection.execute(select(ConversationMedia.media_id)).scalar_one() == "upload"
    )


@pytest.mark.parametrize(
    "model,payload",
    [
        (Conversation, dict(id=uuid4(), session_id=uuid4())),
        (
            Message,
            dict(id=uuid4(), conversation_id=uuid4(), role="user", content="Hello"),
        ),
        (
            TrendCache,
            dict(
                query_hash="c" * 64,
                query="food",
                retrieved_at=datetime(2026, 10, 3, tzinfo=UTC),
                expires_at=datetime(2026, 10, 5, tzinfo=UTC),
            ),
        ),
    ],
)
def test_orphan_context_and_excess_cache_lifetime_rejected(context, model, payload):
    connection, *_ = context
    with pytest.raises(IntegrityError):
        with connection.begin_nested():
            connection.execute(insert(model), payload)


@pytest.mark.asyncio
async def test_supported_checkpoint_setup_is_idempotent_and_threads_persist(
    database_url,
):
    from typing import TypedDict

    from langgraph.graph import END, START, StateGraph

    class State(TypedDict):
        count: int

    await setup_checkpoints(database_url)
    await setup_checkpoints(database_url)
    first, second = str(uuid4()), str(uuid4())
    async with checkpoint_saver(database_url) as saver:
        graph = StateGraph(State)
        graph.add_node("increment", lambda state: {"count": state["count"] + 1})
        graph.add_edge(START, "increment")
        graph.add_edge("increment", END)
        compiled = graph.compile(checkpointer=saver)
        await compiled.ainvoke({"count": 1}, {"configurable": {"thread_id": first}})
        await compiled.ainvoke({"count": 8}, {"configurable": {"thread_id": second}})
    async with checkpoint_saver(database_url) as saver:
        assert (await saver.aget({"configurable": {"thread_id": first}}))[
            "channel_values"
        ]["count"] == 2
        assert (await saver.aget({"configurable": {"thread_id": second}}))[
            "channel_values"
        ]["count"] == 9
        await saver.adelete_thread(first)
        await saver.adelete_thread(second)
