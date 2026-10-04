"""Owned UUID threads, one active turn and explicit cancellation; never resume on read."""

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID, uuid4

from langchain_core.runnables import RunnableConfig
from langgraph.graph.state import CompiledStateGraph

from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.reliability import (
    RunBudget,
    RunLimits,
    current_budget,
)
from food_recommender.application.workflow import ConversationRuns, TurnRequest


@dataclass
class ActiveRun:
    session_id: UUID
    task: asyncio.Task[Any]


class GraphRunner:
    def __init__(
        self,
        graph: CompiledStateGraph[Any, Any, Any, Any],
        runs: ConversationRuns,
        *,
        new_id: Callable[[], UUID] = uuid4,
        limits: RunLimits = RunLimits(),
    ) -> None:
        self.graph, self.runs, self.new_id = graph, runs, new_id
        self.limits = limits
        self.active: dict[UUID, ActiveRun] = {}

    async def run(
        self, session_id: UUID, conversation_id: UUID, request: TurnRequest
    ) -> dict[str, Any]:
        if not isinstance(session_id, UUID) or not isinstance(conversation_id, UUID):
            raise ApplicationError(ErrorCode.INVALID_REQUEST)
        if conversation_id in self.active:
            raise ApplicationError(ErrorCode.CONFLICT)
        task = asyncio.current_task()
        if task is None:
            raise RuntimeError("Run requires an asyncio task")
        self.active[conversation_id] = ActiveRun(session_id, task)
        config: RunnableConfig = {"configurable": {"thread_id": str(conversation_id)}}
        try:
            async with self.runs.lease(conversation_id, session_id):
                state = await self.graph.aget_state(config)
                if state.values and state.values.get("session_id") != str(session_id):
                    raise ApplicationError(ErrorCode.NOT_FOUND)
                budget = RunBudget(self.limits)
                token = current_budget.set(budget)
                run_id = self.new_id()
                try:
                    async with asyncio.timeout(budget.remaining()):
                        result = await self.graph.ainvoke(
                            {
                                "request": request.model_dump(
                                    mode="json", exclude_unset=True
                                ),
                                "conversation_id": str(conversation_id),
                                "session_id": str(session_id),
                                "run_id": str(run_id),
                                "lifecycle": "running",
                            },
                            config,
                        )
                    updates = {"lifecycle": "completed", "metrics": budget.summary()}
                    await self.graph.aupdate_state(
                        config, updates, as_node="recommendation"
                    )
                    logging.getLogger("foodwise").info(
                        "",
                        extra={
                            "event": "run_completed",
                            "run_id": run_id,
                            **budget.summary(),
                        },
                    )
                    return {**dict(result), **updates}
                except TimeoutError:
                    updates = {
                        "lifecycle": "exhausted",
                        "metrics": budget.summary(),
                        "final": {
                            "status": "failure",
                            "code": "budget_exhausted",
                            "retryable": False,
                        },
                    }
                    await self.graph.aupdate_state(
                        config, updates, as_node="recommendation"
                    )
                    logging.getLogger("foodwise").info(
                        "",
                        extra={
                            "event": "run_exhausted",
                            "run_id": run_id,
                            **budget.summary(),
                        },
                    )
                    saved = await self.graph.aget_state(config)
                    return dict(saved.values)
                except asyncio.CancelledError:
                    await self.graph.aupdate_state(
                        config,
                        {
                            "lifecycle": "cancelled",
                            "metrics": budget.summary(),
                            "final": {
                                "status": "failure",
                                "code": "cancelled",
                                "retryable": False,
                            },
                        },
                        as_node="recommendation",
                    )
                    raise
                finally:
                    current_budget.reset(token)
        finally:
            self.active.pop(conversation_id, None)

    async def read(self, session_id: UUID, conversation_id: UUID) -> dict[str, Any]:
        # Ownership and process exclusion are checked before touching a checkpoint.
        async with self.runs.lease(conversation_id, session_id):
            state = await self.graph.aget_state(
                {"configurable": {"thread_id": str(conversation_id)}}
            )
            if state.values and state.values.get("session_id") != str(session_id):
                raise ApplicationError(ErrorCode.NOT_FOUND)
            return dict(state.values)

    async def cancel(self, session_id: UUID, conversation_id: UUID) -> bool:
        active = self.active.get(conversation_id)
        if active is None:
            await self.read(session_id, conversation_id)
            return False
        if active.session_id != session_id:
            raise ApplicationError(ErrorCode.NOT_FOUND)
        active.task.cancel()
        await asyncio.gather(active.task, return_exceptions=True)
        return True
