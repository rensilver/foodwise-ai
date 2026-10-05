"""Exporter failures, privacy, concurrent hierarchy and current API pagination."""

import asyncio
from collections import Counter
from uuid import uuid4

import httpx
import pytest
from scripts.phase10_acceptance import audit_state, load_labels
from scripts.phase10_tracing import CaptureExporter, traced_case

from food_recommender.infrastructure.telemetry.audit import fetch_observations
from food_recommender.infrastructure.telemetry.config import TelemetrySettings
from food_recommender.infrastructure.telemetry.langfuse import LazyTracing, sdk_factory


def settings(**updates):
    base = TelemetrySettings(
        LANGFUSE_ENABLED=True,
        LANGFUSE_BASE_URL="https://us.cloud.langfuse.com",
        LANGFUSE_PUBLIC_KEY=uuid4().hex,
        LANGFUSE_SECRET_KEY="synthetic-secret",
        LANGFUSE_CORRELATION_KEY="synthetic-correlation",
        LANGFUSE_CONVERSATION_EXPORT_VERIFIED=True,
    )
    return base.model_copy(update=updates)


def tracing_for(exporter):
    return LazyTracing(settings(), factory=lambda value: sdk_factory(value, exporter))


@pytest.mark.asyncio
@pytest.mark.parametrize("failure", [401, 429, 503, "timeout"])
async def test_unreachable_invalid_keys_and_quota_do_not_change_results(failure):
    import requests
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

    sent = []

    class Session(requests.Session):
        def request(self, method, url, **kwargs):
            sent.append(kwargs["data"])
            if failure == "timeout":
                raise requests.exceptions.Timeout("PRIVATE_CANARY_EXCEPTION")
            response = requests.Response()
            response.status_code = failure
            response._content = b"PRIVATE_CANARY_CLOUD_ERROR"
            response.url = url
            return response

    exporter = OTLPSpanExporter(
        endpoint="https://fixture.invalid/traces", session=Session(), timeout=0.05
    )
    case = load_labels()["cases"][0]
    disabled, _ = await traced_case(case, LazyTracing(TelemetrySettings()))
    tracing = tracing_for(exporter)
    enabled, _ = await traced_case(case, tracing)
    tracing.client.flush()
    assert sent
    assert all(b"PRIVATE_CANARY" not in body for body in sent)
    assert enabled[0]["final"] == disabled[0]["final"]
    assert not any(audit_state(enabled[0]).values())
    await tracing.close()


@pytest.mark.asyncio
async def test_concurrent_full_early_retry_repair_cancel_have_isolated_parentage():
    capture = CaptureExporter()
    tracing = tracing_for(capture)
    cases = load_labels()["cases"]
    early = next(c for c in cases if c["turns"][0]["expected"] == "clarification")
    outcomes = await asyncio.gather(
        traced_case(cases[0], tracing),
        traced_case(early, tracing),
        traced_case(cases[0], tracing, retry=True),
        traced_case(cases[0], tracing, malformed=True),
        traced_case(cases[0], tracing, cancel=True),
    )
    tracing.client.flush()
    by_id = {span.context.span_id: span for span in capture.spans}
    roots = [span for span in capture.spans if span.name == "recommend-food"]
    assert len(roots) == 5
    for span in capture.spans:
        if span.parent:
            parent = by_id[span.parent.span_id]
            assert parent.context.trace_id == span.context.trace_id
            assert parent.attributes["session.id"] == span.attributes["session.id"]
    early_id = int(outcomes[1][1][0], 16)
    assert Counter(
        span.name for span in capture.spans if span.context.trace_id == early_id
    ) == {"recommend-food": 1, "build-profile": 1, "request-structured-response": 1}
    cancelled_id = int(outcomes[-1][1][0], 16)
    cancelled = [s for s in capture.spans if s.context.trace_id == cancelled_id]
    assert all(
        s.attributes["langfuse.observation.metadata.outcome"] == "cancelled"
        for s in cancelled
    )
    assert not any(audit_state(outcomes[0][0][0]).values())
    await tracing.close()


def test_cursor_pagination_keeps_window_and_fetches_content_fields():
    calls = []

    def respond(request):
        calls.append(dict(request.url.params))
        return httpx.Response(
            200,
            json={
                "data": [{"id": str(len(calls))}],
                "meta": {"cursor": "next" if len(calls) == 1 else None},
            },
        )

    with httpx.Client(
        base_url="https://fixture.invalid", transport=httpx.MockTransport(respond)
    ) as client:
        rows = fetch_observations(client, "a" * 32, "start", "end")
    assert len(rows) == 2
    assert calls[1]["cursor"] == "next"
    assert calls[0]["fromStartTime"] == calls[1]["fromStartTime"]
    assert "io" in calls[0]["fields"]


def test_repeated_cursor_cannot_loop():
    with httpx.Client(
        base_url="https://fixture.invalid",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"data": [], "meta": {"cursor": "same"}}
            )
        ),
    ) as client:
        with pytest.raises(ValueError, match="Repeated"):
            fetch_observations(client, "a" * 32, "start", "end")


def test_disabled_import_and_run_have_no_sdk_threads_or_network():
    import subprocess
    import sys

    script = """
import socket, threading, sys
from uuid import uuid4
from food_recommender.infrastructure.telemetry.config import TelemetrySettings
from food_recommender.infrastructure.telemetry.langfuse import LazyTracing
before = {t.ident for t in threading.enumerate()}
def forbidden(*args, **kwargs): raise AssertionError('network')
socket.socket.connect = forbidden
socket.getaddrinfo = forbidden
with LazyTracing(TelemetrySettings()).run(uuid4(), uuid4()): pass
assert before == {t.ident for t in threading.enumerate()}
assert 'langfuse' not in sys.modules
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr


def test_backpressure_drops_spans_without_blocking_application(monkeypatch):
    import threading
    import time

    from opentelemetry.sdk.trace.export import SpanExportResult

    monkeypatch.setenv("OTEL_BSP_MAX_QUEUE_SIZE", "32")
    entered, release = threading.Event(), threading.Event()

    class Slow:
        def export(self, spans):
            entered.set()
            release.wait(2)
            return SpanExportResult.SUCCESS

        def shutdown(self):
            pass

    tracing = tracing_for(Slow())
    with tracing.run(uuid4(), uuid4()):
        for _ in range(64):
            with tracing.observe("build-profile", "agent"):
                pass
        assert entered.wait(1)
        started = time.monotonic()
        for _ in range(256):
            with tracing.observe("build-profile", "agent"):
                pass
        processor = tracing.client._resources.tracer_provider._active_span_processor._span_processors[
            0
        ]
        assert len(processor._batch_processor._queue) <= 32
        assert time.monotonic() - started < 1
    release.set()
    tracing.client.shutdown()
