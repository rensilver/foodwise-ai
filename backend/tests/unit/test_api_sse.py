"""Real ASGI stream heartbeats, disconnect and iterator cleanup."""

import asyncio
from uuid import uuid4

import pytest

from food_recommender.api.sse import EventStreamResponse, encode_events
from food_recommender.domain.events import DoneEvent


@pytest.mark.asyncio
async def test_heartbeat_does_not_cancel_slow_producer():
    finished = asyncio.Event()

    async def slow():
        await asyncio.sleep(0.02)
        finished.set()
        yield DoneEvent(uuid4(), uuid4(), "completed")

    chunks = [chunk async for chunk in encode_events(slow(), heartbeat_seconds=0.005)]
    assert chunks[0] == b": heartbeat\n\n"
    assert b"event: done" in chunks[-1]
    assert finished.is_set()


@pytest.mark.asyncio
async def test_disconnect_cancels_producer_and_releases_reservation():
    entered, disconnected, cancelled, released = (asyncio.Event() for _ in range(4))

    async def stream():
        try:
            entered.set()
            await asyncio.Event().wait()
            yield b"unreachable"
        finally:
            cancelled.set()

    async def release():
        released.set()

    async def receive():
        await entered.wait()
        disconnected.set()
        return {"type": "http.disconnect"}

    sent = []

    async def send(message):
        sent.append(message)

    response = EventStreamResponse(stream(), release=release)
    await asyncio.wait_for(
        response({"type": "http", "asgi": {"spec_version": "2.4"}}, receive, send), 1
    )
    assert disconnected.is_set() and cancelled.is_set() and released.is_set()
    assert len(sent) == 1
    assert response.headers["x-accel-buffering"] == "no"
    assert response.headers["cache-control"] == "no-store"
