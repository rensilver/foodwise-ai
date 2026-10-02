"""Ports and dependencies for implemented application capabilities."""

from dataclasses import dataclass
from typing import Protocol


class ReadinessProbe(Protocol):
    async def check(self) -> dict[str, bool]:
        """Report bounded local dependency checks, without provider calls."""
        ...


@dataclass(frozen=True)
class Services:
    readiness: ReadinessProbe
