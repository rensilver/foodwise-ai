"""Optional opaque operational trace erasure; no telemetry SDK dependency."""

from typing import Protocol
from uuid import UUID


class ConversationTraceCleanup(Protocol):
    async def request_deletion(self, conversation: UUID) -> None: ...
