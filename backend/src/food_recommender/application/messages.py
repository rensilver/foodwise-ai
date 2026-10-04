"""Owned, replay-protected turns with validated and persisted output events."""

import asyncio
import json
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Literal, Protocol
from uuid import UUID, uuid4

from pydantic import field_validator

from food_recommender.application.activity import Progress
from food_recommender.application.contracts import (
    catalog_adapter,
    event_adapter,
    nutrition_outcome_adapter,
    profile_adapter,
    recommendation_outcome_adapter,
    retrieval_outcome_adapter,
    style_outcome_adapter,
    trend_outcome_adapter,
)
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.evidence_rules import supported_span
from food_recommender.application.nutrition_rules import deterministic_nutrition
from food_recommender.application.ports import UnitOfWork
from food_recommender.application.reliability import RunLimits
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
from food_recommender.domain.experts import AgentFailure, AgentSuccess, ProfileResult
from food_recommender.domain.recommendations import validate_recommendations
from food_recommender.domain.values import Strength


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
    released: bool = False

    async def close(self) -> None:
        if not self.released:
            self.released = True
            await self.lease.__aexit__(None, None, None)


class LocalRuns:
    """Used by injected single-process fixtures; production uses PostgreSQL leases."""

    def __init__(self) -> None:
        self.active: set[UUID] = set()

    @asynccontextmanager
    async def lease(
        self,
        conversation_id: UUID,
        session_id: UUID,
        *,
        protect_context: bool = True,
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
        *,
        limits: RunLimits = RunLimits(),
    ) -> None:
        self.transactions, self.workflow = transactions, workflow
        self.limits = limits
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
                async with asyncio.timeout(self.limits.run_seconds):
                    state = await self.workflow.execute(
                        turn.owner,
                        turn.conversation,
                        turn.run,
                        TurnRequest.model_validate(
                            turn.request.model_dump(exclude={"client_request_id"})
                        ),
                        progress,
                    )
                final, outcome, profile = self._response(turn, state)
                await self._persist(turn, final, profile)
                await queue.put(final)
                await queue.put(DoneEvent(turn.conversation, turn.run, outcome))
            except asyncio.CancelledError:
                raise
            except Exception as error:
                final = ErrorEvent(
                    turn.conversation,
                    turn.run,
                    "budget_exhausted"
                    if isinstance(error, TimeoutError)
                    else "dependency_unavailable"
                    if isinstance(error, ApplicationError)
                    and error.code == ErrorCode.DEPENDENCY_UNAVAILABLE
                    else "internal_error",
                    False,
                )
                try:
                    await self._persist(turn, final, None)
                except Exception:
                    # A failed database cannot attest persistence. Still terminate
                    # safely; the client reads history and never replays this POST.
                    pass
                await queue.put(final)
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
            await turn.close()

    def _response(
        self, turn: PreparedTurn, state: dict[str, Any]
    ) -> tuple[
        ProgressEvents,
        Literal["completed", "clarification", "failed"],
        ProfileResult | None,
    ]:
        final = state.get("final") or {}
        # A failed current extraction must never re-emit a prior clarification.
        if final.get("status") == "failure":
            outcome = recommendation_outcome_adapter.validate_json(json.dumps(final))
            if not isinstance(outcome, AgentFailure):
                raise ValueError("Expected typed failure")
            return (
                ErrorEvent(
                    turn.conversation, turn.run, outcome.code, outcome.retryable
                ),
                "failed",
                None,
            )
        profile = profile_adapter.validate_json(json.dumps(state["profile"]))
        if profile.clarification:
            return (
                ClarificationEvent(turn.conversation, turn.run, profile.clarification),
                "clarification",
                profile,
            )
        result = recommendation_outcome_adapter.validate_json(json.dumps(final))
        if not isinstance(result, AgentSuccess):
            raise ValueError("Missing recommendation result")
        retrieval = retrieval_outcome_adapter.validate_json(
            json.dumps(state["retrieval"])
        )
        if not isinstance(retrieval, AgentSuccess):
            raise ValueError("Missing candidate evidence")
        candidates = catalog_adapter.validate_json(json.dumps(state["catalog"]))
        evidence = tuple(candidate.evidence for candidate in candidates)
        if evidence != retrieval.result.candidates:
            raise ValueError("Canonical and retrieved evidence mismatch")
        validate_recommendations(
            result.result,
            evidence,
            nutrition=deterministic_nutrition(profile, candidates),
            hard_constraints=any(
                c.strength == Strength.HARD for c in profile.preferences.constraints
            ),
        )
        by_entity = {c.entity: c for c in evidence}
        for item in result.result.recommendations:
            if not supported_span(
                item.explanation, by_entity[item.entity].citations, item.citation_ids
            ):
                raise ValueError("Unsupported recommendation explanation")
        return (
            RecommendationsEvent(
                turn.conversation,
                turn.run,
                result.result,
                evidence=evidence,
                trend=trend_outcome_adapter.validate_json(json.dumps(state["trend"])),
                style=style_outcome_adapter.validate_json(json.dumps(state["style"])),
                nutrition=nutrition_outcome_adapter.validate_json(
                    json.dumps(state["nutrition"])
                ),
            ),
            "completed",
            profile,
        )

    async def _persist(
        self, turn: PreparedTurn, final: ProgressEvents, profile: ProfileResult | None
    ) -> None:
        # Validate event payloads before both persistence and transport encoding.
        encoded = event_adapter.dump_json(final)
        event_adapter.validate_json(encoded)
        async with self.transactions() as transaction:
            await transaction.conversations.append_message(
                turn.owner,
                turn.conversation,
                uuid4(),
                "assistant",
                None,
                payload=json.loads(encoded),
                run_id=turn.run,
            )
            if profile:
                await transaction.conversations.save_profile(
                    turn.owner, turn.conversation, profile.preferences
                )
            await transaction.commit()
