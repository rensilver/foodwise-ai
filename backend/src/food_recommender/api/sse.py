"""SSE framing, heartbeats and explicit ASGI disconnect cancellation."""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from anyio import CancelScope
from fastapi.responses import StreamingResponse
from starlette.types import Receive, Scope, Send

from food_recommender.application.recommendations.contracts import event_adapter
from food_recommender.domain.events import ProgressEvents


async def encode_events(
    events: AsyncIterator[ProgressEvents], *, heartbeat_seconds: float = 15
) -> AsyncIterator[bytes]:
    pending = asyncio.ensure_future(anext(events))
    try:
        while True:
            ready, _ = await asyncio.wait({pending}, timeout=heartbeat_seconds)
            if not ready:
                yield b": heartbeat\n\n"
                continue
            try:
                event = pending.result()
            except StopAsyncIteration:
                break
            yield (
                b"event: "
                + event.event.encode()
                + b"\ndata: "
                + event_adapter.dump_json(event)
                + b"\n\n"
            )
            pending = asyncio.ensure_future(anext(events))
    finally:
        with CancelScope(shield=True):
            pending.cancel()
            await asyncio.gather(pending, return_exceptions=True)
            await events.aclose()  # type: ignore[attr-defined]


class EventStreamResponse(StreamingResponse):
    media_type = "text/event-stream"

    def __init__(
        self, stream: AsyncIterator[bytes], *, release: Callable[[], Awaitable[None]]
    ) -> None:
        super().__init__(
            stream,
            media_type="text/event-stream",
            headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
        )
        self.stream, self.release = stream, release

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        streaming = asyncio.create_task(self.stream_response(send))
        disconnected = asyncio.create_task(self.listen_for_disconnect(receive))
        try:
            ready, _ = await asyncio.wait(
                {streaming, disconnected}, return_when=asyncio.FIRST_COMPLETED
            )
            for task in ready:
                task.result()
        except OSError:
            # ASGI 2.4 servers may signal a disconnect by failing send().
            pass
        finally:
            with CancelScope(shield=True):
                streaming.cancel()
                disconnected.cancel()
                await asyncio.gather(streaming, disconnected, return_exceptions=True)
                await self.stream.aclose()  # type: ignore[attr-defined]
                await self.release()
