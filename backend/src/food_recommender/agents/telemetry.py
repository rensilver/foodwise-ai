"""Allowlisted stage telemetry; source/prompt payloads never enter logs."""

import logging
import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import UUID

from food_recommender.agents.state import GraphState
from food_recommender.application.activity import observer
from food_recommender.application.reliability import current_budget
from food_recommender.domain.values import AgentRole


def timed_node(
    stage: str, function: Callable[[GraphState], Awaitable[dict[str, Any]]]
) -> Callable[[GraphState], Awaitable[dict[str, Any]]]:
    async def invoke(state: GraphState) -> dict[str, Any]:
        started = time.monotonic()
        roles = dict(
            zip(
                (
                    "profile",
                    "retrieval",
                    "trend",
                    "style",
                    "nutrition",
                    "recommendation",
                ),
                AgentRole,
                strict=True,
            )
        )
        callback = observer.get()
        if callback:
            await callback(roles[stage], "started")
        updates = await function(state)
        if callback:
            status = (
                updates.get(
                    {"profile": "profile_outcome", "recommendation": "final"}.get(
                        stage, stage
                    )
                )
                or {}
            ).get("status")
            await callback(
                roles[stage],
                "failed"
                if status == "failure"
                else "unavailable"
                if status == "unavailable"
                else "completed",
            )
        budget = current_budget.get()
        if budget:
            duration = (time.monotonic() - started) * 1000
            budget.stages.append(
                {
                    "stage": stage,
                    "duration_ms": duration,
                    "status": (
                        updates.get(
                            {
                                "profile": "profile_outcome",
                                "recommendation": "final",
                            }.get(stage, stage)
                        )
                        or {}
                    ).get("status", "success"),
                }
            )
            if stage == "retrieval":
                budget.retrieval_attempts = (
                    (updates.get("retrieval") or {})
                    .get("result", {})
                    .get("attempts", 0)
                )
            logging.getLogger("foodwise").info(
                "",
                extra={
                    "event": "agent_completed",
                    "run_id": UUID(state["run_id"]) if state.get("run_id") else None,
                    "stage": stage,
                    "duration_ms": duration,
                },
            )
        return updates

    return invoke
