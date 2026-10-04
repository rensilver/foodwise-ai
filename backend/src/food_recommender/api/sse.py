"""HTTP SSE framing for the validated application event contract."""

from collections.abc import AsyncIterator

from food_recommender.application.contracts import event_adapter
from food_recommender.domain.events import ProgressEvents


async def encode_events(events: AsyncIterator[ProgressEvents]) -> AsyncIterator[bytes]:
    async for event in events:
        yield (
            b"event: "
            + event.event.encode()
            + b"\ndata: "
            + event_adapter.dump_json(event)
            + b"\n\n"
        )
