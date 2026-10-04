import asyncio
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest
from langgraph.checkpoint.memory import InMemorySaver
from tests.unit.test_agent_graph import Branch, Profile, Retrieval, Synthesis

from food_recommender.agents.graph import WorkflowRoles, build_graph
from food_recommender.agents.runner import GraphRunner
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.workflow import TurnRequest


class Leases:
    def __init__(self, owner, conversation):
        self.owner, self.conversation = owner, conversation

    @asynccontextmanager
    async def lease(self, conversation_id, session_id):
        if (conversation_id, session_id) != (self.conversation, self.owner):
            raise ApplicationError(ErrorCode.NOT_FOUND)
        yield


class SlowRetrieval(Retrieval):
    def __init__(self):
        self.entered = asyncio.Event()
        self.release = asyncio.Event()

    async def run(self, request, profile):
        self.entered.set()
        await self.release.wait()
        return await super().run(request, profile)


@pytest.mark.asyncio
async def test_concurrent_turn_rejected_cancelled_work_never_resumes_on_read():
    owner, conversation = uuid4(), uuid4()
    started, ready = set(), asyncio.Event()
    branches = [
        Branch(kind, started, ready) for kind in ("trends", "style", "nutrition")
    ]
    retrieval = SlowRetrieval()
    synthesis = Synthesis(branches)
    runner = GraphRunner(
        build_graph(
            WorkflowRoles(Profile(), retrieval, *branches, synthesis),
            checkpointer=InMemorySaver(),
        ),
        Leases(owner, conversation),
    )
    task = asyncio.create_task(
        runner.run(owner, conversation, TurnRequest(message="rice"))
    )
    await asyncio.wait_for(retrieval.entered.wait(), 2)
    with pytest.raises(ApplicationError) as conflict:
        await runner.run(owner, conversation, TurnRequest(message="again"))
    assert conflict.value.code == ErrorCode.CONFLICT
    with pytest.raises(ApplicationError):
        await runner.cancel(uuid4(), conversation)
    assert await runner.cancel(owner, conversation)
    assert task.cancelled()
    state = await runner.read(owner, conversation)
    assert state["lifecycle"] == "cancelled"
    assert synthesis.calls == 0
    assert not await runner.cancel(owner, conversation)
    retrieval.release.set()
    new = await runner.run(owner, conversation, TurnRequest(message="new request"))
    assert new["final"]["status"] == "success"
    assert new["run_id"] != state["run_id"]
    assert synthesis.calls == 1
