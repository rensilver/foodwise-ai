"""Durable tombstones prevent queued exports from recreating erased conversations."""

import pytest

from food_recommender.infrastructure.telemetry.ledger import TraceLedger


def test_tombstones_survive_restart_and_reject_late_exports(tmp_path):
    path = tmp_path / "telemetry.sqlite"
    ledger = TraceLedger(path)
    ledger.register("s" * 64, "a" * 32)
    ledger.tombstone("s" * 64)
    restarted = TraceLedger(path)
    assert not restarted.allowed("a" * 32)
    assert not restarted.register("s" * 64, "b" * 32)
    assert restarted.pending() == ["a" * 32]


@pytest.mark.asyncio
async def test_deleted_conversation_is_erased_from_queued_sdk_export(tmp_path):
    from uuid import uuid4

    from scripts.phase10_tracing import CaptureExporter

    from food_recommender.infrastructure.telemetry.config import TelemetrySettings
    from food_recommender.infrastructure.telemetry.langfuse import (
        LazyTracing,
        sdk_factory,
    )

    path = tmp_path / "ledger.sqlite"
    ledger = TraceLedger(path)
    capture = CaptureExporter()
    settings = TelemetrySettings(
        LANGFUSE_ENABLED=True,
        LANGFUSE_BASE_URL="https://us.cloud.langfuse.com",
        LANGFUSE_PUBLIC_KEY=uuid4().hex,
        LANGFUSE_SECRET_KEY="synthetic",
        LANGFUSE_CORRELATION_KEY="synthetic-correlation",
        LANGFUSE_CONVERSATION_EXPORT_VERIFIED=True,
    )
    tracing = LazyTracing(
        settings,
        ledger_path=path,
        factory=lambda s: sdk_factory(s, capture, ledger=ledger),
    )
    conversation, run = uuid4(), uuid4()
    with tracing.run(run, conversation):
        with tracing.observe("build-profile", "agent"):
            pass
    await tracing.request_deletion(conversation)
    tracing.client.flush()
    assert capture.spans == []
    assert ledger.pending() == [run.hex]
    with tracing.run(uuid4(), conversation):
        pass
    tracing.client.flush()
    assert capture.spans == []
    await tracing.close()


def test_export_lock_prevents_deletion_from_racing_inflight_delivery(tmp_path):
    import threading
    from types import SimpleNamespace

    ledger = TraceLedger(tmp_path / "ledger.sqlite")
    ledger.register("s" * 64, "a" * 32)
    entered, release = threading.Event(), threading.Event()

    def export(spans):
        entered.set()
        release.wait(1)
        return len(spans)

    spans = [SimpleNamespace(context=SimpleNamespace(trace_id=int("a" * 32, 16)))]
    worker = threading.Thread(target=lambda: ledger.filter_and_export(spans, export))
    worker.start()
    assert entered.wait(1)
    import sqlite3

    import pytest

    with pytest.raises(sqlite3.OperationalError):
        ledger.tombstone("s" * 64)
    release.set()
    worker.join(2)
    ledger.tombstone("s" * 64)
    assert ledger.filter_and_export(spans, len) == 0


def test_trace_sampling_keeps_whole_tree_and_scores_consistent():
    from uuid import UUID, uuid4

    from scripts.phase10_tracing import CaptureExporter

    from food_recommender.application.recommendations.tracing import current_tracing
    from food_recommender.infrastructure.telemetry.config import TelemetrySettings
    from food_recommender.infrastructure.telemetry.langfuse import (
        LazyTracing,
        sdk_factory,
    )
    from food_recommender.infrastructure.telemetry.scores import (
        LocalScore,
        score_payload,
    )

    capture = CaptureExporter()
    settings = TelemetrySettings(
        LANGFUSE_ENABLED=True,
        LANGFUSE_BASE_URL="https://us.cloud.langfuse.com",
        LANGFUSE_PUBLIC_KEY=uuid4().hex,
        LANGFUSE_SECRET_KEY="offline",
        LANGFUSE_CORRELATION_KEY="synthetic",
        LANGFUSE_CONVERSATION_EXPORT_VERIFIED=True,
        LANGFUSE_SAMPLE_RATE=0.5,
    )
    tracing = LazyTracing(settings, factory=lambda s: sdk_factory(s, capture))
    selected, omitted = UUID(int=1), UUID(int=2**128 - 1)
    for run in (selected, omitted):
        with tracing.run(run, uuid4()):
            with current_tracing.get().observe("build-profile", "agent"):
                pass
    tracing.client.flush()
    assert len(capture.spans) == 2
    assert {s.context.trace_id for s in capture.spans} == {selected.int}
    assert (
        score_payload(
            LocalScore(
                "expected_outcome", 1, selected, "a" * 16, "fixture", uuid4(), 1
            ),
            sample_rate=0.5,
        )
        is not None
    )
    assert (
        score_payload(
            LocalScore("expected_outcome", 1, omitted, "a" * 16, "fixture", uuid4(), 1),
            sample_rate=0.5,
        )
        is None
    )
    tracing.client.shutdown()


def test_cold_sdk_import_preserves_redacted_logging():
    import subprocess
    import sys

    script = """
import io,logging
from uuid import uuid4
from food_recommender.infrastructure.observability import configure_logging
from food_recommender.infrastructure.telemetry.config import TelemetrySettings
from food_recommender.infrastructure.telemetry.langfuse import sdk_factory
from opentelemetry.sdk.trace.export import SpanExportResult
stream=io.StringIO()
configure_logging(stream=stream)
class Exporter:
    def export(self,spans): return SpanExportResult.SUCCESS
    def shutdown(self): pass
settings=TelemetrySettings(LANGFUSE_ENABLED=True,LANGFUSE_BASE_URL="https://us.cloud.langfuse.com",LANGFUSE_PUBLIC_KEY=uuid4().hex,LANGFUSE_SECRET_KEY="synthetic",LANGFUSE_CORRELATION_KEY="synthetic")
client=sdk_factory(settings,Exporter())
assert not logging.getLogger("httpx").handlers
logging.getLogger("httpx").warning("PRIVATE_CANARY_PROFILE")
assert "PRIVATE_CANARY" not in stream.getvalue()
client.shutdown()
"""
    result = subprocess.run(
        [sys.executable, "-c", script], capture_output=True, text=True, timeout=15
    )
    assert result.returncode == 0, result.stderr
    assert "PRIVATE_CANARY" not in result.stderr
