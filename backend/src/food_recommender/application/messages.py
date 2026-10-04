"""Owned, replay-protected turns with validated and persisted output events."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Protocol
from uuid import UUID, uuid4

from pydantic import field_validator

from food_recommender.application.activity import Progress
from food_recommender.application.contracts import (
    event_adapter,
    profile_adapter,
    recommendation_outcome_adapter,
)
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.ports import UnitOfWork
from food_recommender.application.workflow import (
    ConversationRuns,
    RunLease,
    TurnRequest,
)
from food_recommender.domain.events import (
    ClarificationEvent,
    DoneEvent,
    ErrorEvent,
    ProgressEvent,
    ProgressEvents,
    RecommendationsEvent,
)
from food_recommender.domain.experts import AgentSuccess


class MessageSubmission(TurnRequest):
    client_request_id: UUID

    @field_validator("message")
    @classmethod
    def nonblank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("Message must not be blank")
        return value


class Workflow(Protocol):
    async def execute(
        self,
        owner: UUID,
        conversation: UUID,
        run: UUID,
        request: TurnRequest,
        progress: Progress,
    ) -> dict[str, Any]: ...


@dataclass
class PreparedTurn:
    owner: UUID
    conversation: UUID
    run: UUID
    request: MessageSubmission
    lease: RunLease


class LocalRuns:
    """Used by injected single-process fixtures; production uses PostgreSQL leases."""

    def __init__(self) -> None:
        self.active: set[UUID] = set()

    @asynccontextmanager
    async def lease(
        self, conversation_id: UUID, session_id: UUID
    ) -> AsyncIterator[None]:
        if conversation_id in self.active:
            raise ApplicationError(ErrorCode.CONFLICT)
        self.active.add(conversation_id)
        try:
            yield
        finally:
            self.active.remove(conversation_id)


class MessageService:
    def __init__(
        self,
        transactions: Callable[[], UnitOfWork],
        workflow: Workflow,
        runs: ConversationRuns | None = None,
    ) -> None:
        self.transactions, self.workflow = transactions, workflow
        self.runs = runs if runs is not None else LocalRuns()

    async def prepare(
        self, owner: UUID, conversation: UUID, request: MessageSubmission
    ) -> PreparedTurn:
        # Ownership and media checks happen before HTTP response headers.
        async with self.transactions() as transaction:
            await transaction.conversations.get(owner, conversation)
        lease = self.runs.lease(conversation, owner)
        await lease.__aenter__()
        try:
            run = uuid4()
            async with self.transactions() as transaction:
                if request.media_id:
                    await transaction.conversations.link_media(
                        owner, conversation, request.media_id
                    )
                await transaction.conversations.append_message(
                    owner,
                    conversation,
                    request.client_request_id,
                    "user",
                    request.message,
                    payload=request.model_dump(mode="json"),
                    run_id=run,
                )
                await transaction.commit()
            return PreparedTurn(owner, conversation, run, request, lease)
        except BaseException:
            await lease.__aexit__(None, None, None)
            raise

    async def events(self, turn: PreparedTurn) -> AsyncIterator[ProgressEvents]:
        queue: asyncio.Queue[ProgressEvents | None] = asyncio.Queue()

        async def progress(agent: Any, activity: Any) -> None:
            await queue.put(ProgressEvent(turn.conversation, turn.run, agent, activity))

        async def produce() -> None:
            try:
                state = await self.workflow.execute(
                    turn.owner,
                    turn.conversation,
                    turn.run,
                    TurnRequest.model_validate(
                        turn.request.model_dump(exclude={"client_request_id"})
                    ),
                    progress,
                )
                profile = state.get("profile") or {}
                if profile.get("clarification"):
                    final: ProgressEvents = ClarificationEvent(
                        turn.conversation, turn.run, profile["clarification"]
                    )
                    outcome = "clarification"
                else:
                    result = recommendation_outcome_adapter.validate_json(
                        json.dumps(state.get("final"))
                    )
                    if isinstance(result, AgentSuccess):
                        final = RecommendationsEvent(
                            turn.conversation, turn.run, result.result
                        )
                        outcome = "completed"
                    else:
                        final = ErrorEvent(
                            turn.conversation,
                            turn.run,
                            getattr(result, "code", "internal_error"),
                            getattr(result, "retryable", False),
                        )
                        outcome = "failed"
                async with self.transactions() as transaction:
                    await transaction.conversations.append_message(
                        turn.owner,
                        turn.conversation,
                        uuid4(),
                        "assistant",
                        None,
                        payload=json.loads(event_adapter.dump_json(final)),
                        run_id=turn.run,
                    )
                    if profile.get("preferences") is not None:
                        validated = profile_adapter.validate_json(json.dumps(profile))
                        await transaction.conversations.save_profile(
                            turn.owner, turn.conversation, validated.preferences
                        )
                    await transaction.commit()
                await queue.put(final)
                await queue.put(DoneEvent(turn.conversation, turn.run, outcome))  # type: ignore[arg-type]
            except asyncio.CancelledError:
                raise
            except Exception:
                await queue.put(
                    ErrorEvent(turn.conversation, turn.run, "internal_error", False)
                )
                await queue.put(DoneEvent(turn.conversation, turn.run, "failed"))
            finally:
                await queue.put(None)

        task = asyncio.create_task(produce())
        try:
            while (event := await queue.get()) is not None:
                yield event
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await turn.lease.__aexit__(None, None, None)
