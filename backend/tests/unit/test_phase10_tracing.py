"""Optional tracing must be lazy, isolated and unable to change business behavior."""

from uuid import uuid4

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
