"""Provider-neutral metadata observations, independent of progress and graph state."""

from collections.abc import Iterator
from contextlib import AbstractContextManager, contextmanager
from contextvars import ContextVar
from typing import Protocol
from uuid import UUID


class Observation(Protocol):
    def update(self, **measurements: int | float | str) -> None: ...


class Tracing(Protocol):
    def run(
        self, run: UUID, conversation: UUID
    ) -> AbstractContextManager[Observation]: ...
    def observe(self, name: str, kind: str) -> AbstractContextManager[Observation]: ...


class NoopObservation:
    def update(self, **measurements: int | float | str) -> None:
        pass


class NoopTracing:
    @contextmanager
    def run(self, run: UUID, conversation: UUID) -> Iterator[Observation]:
        yield NoopObservation()

    @contextmanager
    def observe(self, name: str, kind: str) -> Iterator[Observation]:
        yield NoopObservation()


current_tracing: ContextVar[Tracing] = ContextVar(
    "foodwise_tracing", default=NoopTracing()
)
