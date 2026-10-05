"""Owned real six-role threads and cross-process run exclusion in PostgreSQL."""

import asyncio
from pathlib import Path
from uuid import uuid4

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from sqlalchemy import delete, insert
from sqlalchemy.ext.asyncio import async_sessionmaker
from tests.unit.agent_fixtures import Reply
from tests.unit.test_agent_graph import Branch, Retrieval, Synthesis

from food_recommender.agents.graph import WorkflowRoles, build_graph
from food_recommender.agents.nodes.profile import UserProfileGenerator
from food_recommender.agents.runner import GraphRunner
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.recommendations.workflow import TurnRequest
from food_recommender.infrastructure.persistence.checkpoints import (
    checkpoint_saver,
    setup_checkpoints,
)
from food_recommender.infrastructure.persistence.engine import create_database_engine
from food_recommender.infrastructure.persistence.models.context import (
    BrowserSession,
    Conversation,
)
from food_recommender.infrastructure.persistence.runs import PostgresConversationRuns


@pytest_asyncio.fixture
async def workflow_store(database_url):
    engine = create_database_engine(database_url)
    config = Config(str(Path(__file__).parents[2] / "alembic.ini"))
    async with engine.begin() as connection:

        def migrate(sync):
            config.attributes["connection"] = sync
            command.upgrade(config, "head")

        await connection.run_sync(migrate)
    owner, stranger, conversation = uuid4(), uuid4(), uuid4()
    async with async_sessionmaker(engine).begin() as session:
        await session.execute(
            insert(BrowserSession),
            [
                {"id": owner, "token_hash": uuid4().hex * 2},
                {"id": stranger, "token_hash": uuid4().hex * 2},
            ],
        )
        await session.execute(
            insert(Conversation).values(id=conversation, session_id=owner)
        )
    await setup_checkpoints(database_url)
    try:
        yield engine, owner, stranger, conversation
    finally:
        async with checkpoint_saver(database_url) as saver:
            await saver.adelete_thread(str(conversation))
        async with engine.begin() as connection:
            await connection.execute(
                delete(Conversation).where(Conversation.id == conversation)
            )
            await connection.execute(
                delete(BrowserSession).where(BrowserSession.id.in_((owner, stranger)))
            )

            def downgrade(sync):
                config.attributes["connection"] = sync
                command.downgrade(config, "base")

            await connection.run_sync(downgrade)
        await engine.dispose()


def roles():
    started, ready = set(), asyncio.Event()
    branches = [
        Branch(kind, started, ready) for kind in ("trends", "style", "nutrition")
    ]
    return WorkflowRoles(
        UserProfileGenerator(Reply({})), Retrieval(), *branches, Synthesis(branches)
    )


@pytest.mark.asyncio
async def test_actual_graph_checkpoint_restart_and_owner_isolation(
    database_url, workflow_store
):
    engine, owner, stranger, conversation = workflow_store
    leases = PostgresConversationRuns(engine)
    async with checkpoint_saver(database_url) as saver:
        # JSON-only state must work with strict serializer allowlists.
        saver.serde = JsonPlusSerializer(allowed_msgpack_modules=None)
        runner = GraphRunner(build_graph(roles(), checkpointer=saver), leases)
        first = await runner.run(
            owner,
            conversation,
            TurnRequest(
                message="rice",
                categories=["recipe"],
                explicit={
                    "constraints": [
                        {
                            "kind": "allergen",
                            "value": "peanut",
                            "strength": "hard",
                            "origin": "explicit",
                        }
                    ]
                },
            ),
        )
        with pytest.raises(ApplicationError) as denied:
            await runner.read(stranger, conversation)
        assert denied.value.code == ErrorCode.NOT_FOUND
    async with checkpoint_saver(database_url) as saver:
        saver.serde = JsonPlusSerializer(allowed_msgpack_modules=None)
        runner = GraphRunner(build_graph(roles(), checkpointer=saver), leases)
        second = await runner.run(
            owner, conversation, TurnRequest(message="now Italian")
        )
        assert (
            second["profile"]["preferences"]["constraints"]
            == first["profile"]["preferences"]["constraints"]
        )
        assert second["run_id"] != first["run_id"]
        assert "rice" in second["messages"]
        assert (await runner.read(owner, conversation))["lifecycle"] == "completed"


@pytest.mark.asyncio
async def test_two_adapters_contend_for_one_database_run_lease(workflow_store):
    engine, owner, stranger, conversation = workflow_store
    first, second = PostgresConversationRuns(engine), PostgresConversationRuns(engine)
    async with first.lease(conversation, owner):
        with pytest.raises(ApplicationError) as conflict:
            async with second.lease(conversation, owner):
                pytest.fail("Concurrent run acquired the lease")
        assert conflict.value.code == ErrorCode.CONFLICT
        with pytest.raises(ApplicationError) as denied:
            async with second.lease(conversation, stranger):
                pytest.fail("Stranger acquired the lease")
        assert denied.value.code == ErrorCode.NOT_FOUND
    async with second.lease(conversation, owner):
        pass


@pytest.mark.asyncio
async def test_cancelled_real_checkpoint_can_only_restart_on_explicit_new_turn(
    database_url, workflow_store
):
    from tests.unit.test_agent_runner import SlowRetrieval

    engine, owner, stranger, conversation = workflow_store
    retrieval = SlowRetrieval()
    actual = roles()
    controlled = WorkflowRoles(
        actual.profile,
        retrieval,
        actual.trend,
        actual.style,
        actual.nutrition,
        actual.recommendation,
    )
    async with checkpoint_saver(database_url) as saver:
        runner = GraphRunner(
            build_graph(controlled, checkpointer=saver),
            PostgresConversationRuns(engine),
        )
        task = asyncio.create_task(
            runner.run(owner, conversation, TurnRequest(message="rice"))
        )
        await asyncio.wait_for(retrieval.entered.wait(), 2)
        assert await runner.cancel(owner, conversation)
        assert task.cancelled()
    async with checkpoint_saver(database_url) as saver:
        runner = GraphRunner(
            build_graph(roles(), checkpointer=saver), PostgresConversationRuns(engine)
        )
        saved = await runner.read(owner, conversation)
        assert saved["lifecycle"] == "cancelled"
        assert saved["final"]["code"] == "cancelled"
        resumed = await runner.run(
            owner, conversation, TurnRequest(message="explicit new request")
        )
        assert resumed["run_id"] != saved["run_id"]
        assert resumed["final"]["status"] == "success"
