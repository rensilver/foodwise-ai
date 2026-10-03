"""Ports and dependencies for implemented application capabilities."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

from food_recommender.application.ports import UnitOfWork


class ReadinessProbe(Protocol):
    async def check(self) -> dict[str, bool]:
        """Report bounded local dependency checks, without provider calls."""
        ...


@dataclass(frozen=True)
class Services:
    readiness: ReadinessProbe
    transactions: Callable[[], UnitOfWork] | None = None
    close: Callable[[], Awaitable[None]] | None = None
