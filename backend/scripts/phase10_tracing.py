"""Synthetic tracing harness: real graph/SDK/provider adapter, mocked HTTP responses."""

import asyncio
import json
from uuid import uuid4

import httpx
from pydantic import SecretStr
from scripts.phase10_acceptance import (
    FixtureInference,
    FixtureTools,
    OwnedLeases,
    fixture_runner,
)

from food_recommender.application.recommendations.workflow import TurnRequest
from food_recommender.infrastructure.providers.openai import OpenAIStructuredInference


class CaptureExporter:
    def __init__(self, destination=None):
        self.destination = destination
        self.spans = []
        self.bytes = 0
        self.calls = 0
        self.max_batch = 0
        self.max_bytes = 0

    def export(self, spans):
        from food_recommender.infrastructure.telemetry.redaction import sanitized_span

        spans = [item for span in spans if (item := sanitized_span(span)) is not None]
        from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
        from opentelemetry.sdk.trace.export import SpanExportResult

        data = encode_spans(spans).SerializeToString()
        if b"PRIVATE_CANARY" in data or b"data:image" in data:
            raise AssertionError("Synthetic private content reached export")
        self.max_batch = max(self.max_batch, len(spans))
        self.max_bytes = max(self.max_bytes, len(data))
        self.bytes += len(data)
        self.calls += 1
        self.spans.extend(spans)
        return (
            self.destination.export(spans)
            if self.destination
            else SpanExportResult.SUCCESS
        )

    def shutdown(self):
        if self.destination:
            self.destination.shutdown()


async def traced_case(case, tracing, *, retry=False, malformed=False, cancel=False):
    owner, conversation = uuid4(), uuid4()
    fixture = FixtureInference()
    tools = FixtureTools(case)
    requests = 0
    entered = asyncio.Event()

    async def respond(request):
        nonlocal requests
        requests += 1
        entered.set()
        if cancel:
            await asyncio.Event().wait()
        if retry and requests == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        body = json.loads(request.content)
        content = (
            "broken PRIVATE_CANARY"
            if malformed and requests == 1
            else await fixture.generate(
                body["messages"], body["response_format"]["json_schema"]["schema"]
            )
        )
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": content}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 10,
                    "completion_tokens": 2,
                    "total_tokens": 12,
                },
            },
        )

    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as http:
        provider = OpenAIStructuredInference(
            http, SecretStr("PRIVATE_CANARY_KEY"), "gpt-4o-mini"
        )
        runner = fixture_runner(provider, tools, OwnedLeases({conversation: owner}))
        runner.tracing = tracing
        states, runs = [], []
        for turn in case["turns"]:
            fixture.patch = turn["profile_patch"]
            run = uuid4()
            runs.append(run.hex)
            task = asyncio.create_task(
                runner.run(
                    owner,
                    conversation,
                    TurnRequest.model_validate(turn["request"]),
                    run_id=run,
                )
            )
            if cancel:
                await asyncio.wait_for(entered.wait(), 2)
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
                saved = await runner.read(owner, conversation)
                assert saved["lifecycle"] == "cancelled"
                states.append(saved)
                break
            states.append(await task)
    return states, runs


def bounded_sdk_call(function, seconds=3):
    import threading

    done = threading.Event()
    successful = []

    def invoke():
        try:
            function()
            successful.append(True)
        except Exception:
            pass
        finally:
            done.set()

    threading.Thread(target=invoke, daemon=True, name="foodwise-audit-flush").start()
    return done.wait(seconds) and bool(successful)
