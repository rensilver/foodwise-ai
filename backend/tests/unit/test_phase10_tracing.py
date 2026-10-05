"""Optional tracing must be lazy, isolated and unable to change business behavior."""

from uuid import uuid4

import pytest

from food_recommender.infrastructure.telemetry.config import TelemetrySettings
from food_recommender.infrastructure.telemetry.langfuse import LazyTracing


def test_disabled_tracing_never_constructs_sdk():
    def forbidden(*args, **kwargs):
        raise AssertionError("SDK initialized while disabled")

    tracing = LazyTracing(TelemetrySettings(), factory=forbidden)
    with tracing.run(uuid4(), uuid4()):
        pass
    assert tracing.client is None


def enabled_settings(**overrides):
    return TelemetrySettings(
        LANGFUSE_ENABLED=True,
        LANGFUSE_BASE_URL="https://us.cloud.langfuse.com",
        LANGFUSE_PUBLIC_KEY="synthetic-public",
        LANGFUSE_SECRET_KEY="synthetic-secret",
        LANGFUSE_CORRELATION_KEY="synthetic-correlation",
        LANGFUSE_CONVERSATION_EXPORT_VERIFIED=True,
        **overrides,
    )


def test_credentials_do_not_enable_conversation_export():
    settings = enabled_settings().model_copy(
        update={"conversation_export_verified": False}
    )
    tracing = LazyTracing(
        settings, factory=lambda settings: (_ for _ in ()).throw(AssertionError())
    )
    with tracing.run(uuid4(), uuid4()):
        pass
    assert not tracing.attempted


def test_initialization_failure_preserves_business_execution():
    calls = []

    def failing(settings):
        calls.append(1)
        raise RuntimeError("PRIVATE_EXCEPTION")

    tracing = LazyTracing(enabled_settings(), factory=failing)
    for _ in range(2):
        with tracing.run(uuid4(), uuid4()):
            pass
    assert calls == [1]


def test_real_sdk_export_rebuilds_metadata_and_discards_events():
    from opentelemetry.exporter.otlp.proto.common.trace_encoder import encode_spans
    from opentelemetry.proto.collector.trace.v1.trace_service_pb2 import (
        ExportTraceServiceRequest,
    )
    from opentelemetry.sdk.trace.export import SpanExportResult

    from food_recommender.infrastructure.telemetry.langfuse import sdk_factory

    class Capture:
        spans = []

        def export(self, spans):
            self.spans.extend(spans)
            return SpanExportResult.SUCCESS

        def shutdown(self):
            pass

    capture = Capture()
    tracing = LazyTracing(
        enabled_settings(), factory=lambda settings: sdk_factory(settings, capture)
    )
    run, conversation = uuid4(), uuid4()
    with tracing.run(run, conversation) as root:
        root.update(outcome="success", duration_ms=1)
        with tracing.observe("build-profile", "agent") as stage:
            stage.span.update(
                input="PRIVATE_PROFILE",
                output="PRIVATE_IMAGE",
                metadata={"secret": "PRIVATE_KEY"},
            )
            stage.span._otel_span.add_event(
                "PRIVATE_EXCEPTION", {"secret": "PRIVATE_EVENT"}
            )
    tracing.client.flush()
    assert {s.name for s in capture.spans} == {"recommend-food", "build-profile"}
    data = encode_spans(capture.spans).SerializeToString()
    assert all(value not in data for value in [b"PRIVATE_", str(conversation).encode()])
    assert all(not s.events and not s.resource.attributes for s in capture.spans)
    parsed = ExportTraceServiceRequest.FromString(data)
    assert len(parsed.resource_spans) == 1
    tracing.client.shutdown()


async def capture_graph(case, tracing):
    from scripts.phase10_acceptance import (
        FixtureInference,
        FixtureTools,
        OwnedLeases,
        fixture_runner,
    )

    from food_recommender.application.recommendations.workflow import TurnRequest

    owner, conversation = uuid4(), uuid4()
    provider, tools = FixtureInference(), FixtureTools(case)
    runner = fixture_runner(provider, tools, OwnedLeases({conversation: owner}))
    runner.tracing = tracing
    states = []
    for turn in case["turns"]:
        provider.patch = turn["profile_patch"]
        states.append(
            await runner.run(
                owner, conversation, TurnRequest.model_validate(turn["request"])
            )
        )
    return states


@pytest.mark.asyncio
async def test_parallel_graph_stages_have_one_root_and_no_duplicate_synthesis():
    from opentelemetry.sdk.trace.export import SpanExportResult
    from scripts.phase10_acceptance import load_labels

    from food_recommender.infrastructure.telemetry.langfuse import sdk_factory

    class Capture:
        spans = []

        def export(self, spans):
            self.spans.extend(spans)
            return SpanExportResult.SUCCESS

        def shutdown(self):
            pass

    capture = Capture()
    settings = enabled_settings().model_copy(
        update={"public_key": __import__("pydantic").SecretStr(uuid4().hex)}
    )
    tracing = LazyTracing(
        settings, factory=lambda settings: sdk_factory(settings, capture)
    )
    states = await capture_graph(load_labels()["cases"][0], tracing)
    tracing.client.flush()
    assert states[0]["final"]["status"] == "success"
    roots = [span for span in capture.spans if span.name == "recommend-food"]
    assert len(roots) == 1
    agents = [
        span
        for span in capture.spans
        if span.attributes["langfuse.observation.type"] == "agent"
    ]
    assert len(agents) == 6
    assert all(span.parent.span_id == roots[0].context.span_id for span in agents)
    assert (
        len([span for span in agents if span.name == "synthesize-recommendations"]) == 1
    )
    assert all(span.attributes.get("session.id") for span in capture.spans)
    tracing.client.shutdown()


@pytest.mark.asyncio
async def test_actual_openai_attempts_have_individual_usage_and_retry_parentage():
    import httpx
    from opentelemetry.sdk.trace.export import SpanExportResult
    from pydantic import SecretStr

    from food_recommender.application.recommendations.reliability import (
        BudgetedInference,
    )
    from food_recommender.infrastructure.providers.openai import (
        OpenAIStructuredInference,
    )
    from food_recommender.infrastructure.telemetry.langfuse import sdk_factory

    class Capture:
        spans = []

        def export(self, spans):
            self.spans.extend(spans)
            return SpanExportResult.SUCCESS

        def shutdown(self):
            pass

    capture = Capture()
    count = 0

    def respond(request):
        nonlocal count
        count += 1
        if count == 1:
            return httpx.Response(429, headers={"Retry-After": "0"})
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "{}"}, "finish_reason": "stop"}],
                "usage": {
                    "prompt_tokens": 7,
                    "completion_tokens": 3,
                    "total_tokens": 10,
                },
            },
        )

    tracing = LazyTracing(
        enabled_settings().model_copy(update={"public_key": SecretStr(uuid4().hex)}),
        factory=lambda settings: sdk_factory(settings, capture),
    )
    async with httpx.AsyncClient(transport=httpx.MockTransport(respond)) as client:
        provider = BudgetedInference(
            OpenAIStructuredInference(client, SecretStr("PRIVATE_KEY"), "gpt-4o-mini"),
            sleep=lambda seconds: __import__("asyncio").sleep(0),
            jitter=lambda: 0,
        )
        with tracing.run(uuid4(), uuid4()):
            with tracing.observe("build-profile", "agent"):
                assert (
                    await provider.generate(
                        [{"role": "user", "content": "PRIVATE_PROMPT"}], {}
                    )
                    == "{}"
                )
    tracing.client.flush()
    generations = [s for s in capture.spans if s.name == "request-structured-response"]
    assert len(generations) == 2 == count
    assert {
        s.attributes["langfuse.observation.metadata.attempt"] for s in generations
    } == {1, 2}
    used = [
        s for s in generations if "langfuse.observation.usage_details" in s.attributes
    ]
    assert len(used) == 1
    assert __import__("json").loads(
        used[0].attributes["langfuse.observation.usage_details"]
    ) == {"input": 7, "output": 3, "total": 10}
    assert all(
        s.parent.span_id
        == next(s for s in capture.spans if s.name == "build-profile").context.span_id
        for s in generations
    )
    tracing.client.shutdown()
