"""Lazy, failure-isolated explicit SDK observations with metadata-only OTLP export."""

import asyncio
import hashlib
import hmac
import logging
import os
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from typing import Any
from uuid import UUID

from food_recommender.application.recommendations.tracing import (
    NoopObservation,
    Observation,
    current_tracing,
)
from food_recommender.infrastructure.telemetry.config import TelemetrySettings
from food_recommender.infrastructure.telemetry.scores import trace_selected
from food_recommender.infrastructure.telemetry.redaction import (
    COUNTERS,
    KINDS,
    NAMES,
    OUTCOMES,
    sanitized_span,
)


class SafeObservation:
    def __init__(self, span: Any) -> None:
        self.span = span

    def update(self, **measurements: int | float | str) -> None:
        metadata = {
            k: v
            for k, v in measurements.items()
            if k in COUNTERS or k == "outcome" and v in OUTCOMES
        }
        try:
            extra: dict[str, Any] = {}
            if isinstance(measurements.get("model"), str):
                extra["model"] = measurements["model"]
            usage = {
                target: measurements[source]
                for source, target in (
                    ("input_tokens", "input"),
                    ("output_tokens", "output"),
                    ("total_tokens", "total"),
                )
                if isinstance(measurements.get(source), int)
            }
            if usage:
                extra["usage_details"] = usage
            self.span.update(metadata=metadata, **extra)
        except Exception:
            diagnostic()


def diagnostic() -> None:
    logging.getLogger("foodwise").info("", extra={"event": "diagnostic"})


def sdk_factory(settings: TelemetrySettings, exporter: Any = None) -> Any:
    import base64

    import requests
    from langfuse import Langfuse
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SpanExporter, SpanExportResult

    class SafeExporter(SpanExporter):
        def export(self, spans: Any) -> Any:
            try:
                clean = [
                    item for span in spans if (item := sanitized_span(span)) is not None
                ]
                return destination.export(clean) if clean else SpanExportResult.SUCCESS
            except Exception:
                diagnostic()
                return SpanExportResult.FAILURE

        def shutdown(self) -> None:
            destination.shutdown()  # type: ignore[no-untyped-call]

    if exporter is None:
        assert settings.public_key and settings.secret_key
        auth = base64.b64encode(
            f"{settings.public_key.get_secret_value()}:{settings.secret_key.get_secret_value()}".encode()
        ).decode()
        destination = OTLPSpanExporter(
            endpoint=f"{settings.base_url}/api/public/otel/v1/traces",
            headers={
                "Authorization": f"Basic {auth}",
                "x-langfuse-ingestion-version": "4",
            },
            timeout=2,
            max_request_size=256 * 1024,
            session=requests.Session(),
        )
    else:
        destination = exporter
    # SDK 4.16.0 uses OTel's bounded BSP queue. Reject ambient settings that
    # would exceed the reviewed bound instead of silently accepting larger queues.
    queue_size = int(os.environ.get("OTEL_BSP_MAX_QUEUE_SIZE", "2048"))
    if not 32 <= queue_size <= 2048:
        raise ValueError("Telemetry queue outside reviewed bounds")
    client = Langfuse(
        public_key=settings.public_key.get_secret_value()
        if settings.public_key
        else "offline-public",
        secret_key=settings.secret_key.get_secret_value()
        if settings.secret_key
        else "offline-secret",
        base_url=settings.base_url,
        timeout=2,
        flush_at=32,
        flush_interval=1,
        environment=settings.environment,
        release=settings.revision,
        sample_rate=1,
        tracer_provider=TracerProvider(resource=Resource({})),
        span_exporter=SafeExporter(),
        should_export_span=lambda span: span.name in NAMES,
    )
    return client


class LazyTracing:
    def __init__(
        self,
        settings: TelemetrySettings,
        *,
        factory: Callable[..., Any] = sdk_factory,
        revisions: dict[str, str] | None = None,
    ) -> None:
        self.settings, self.factory = settings, factory
        self.revisions = revisions or {}
        self.client: Any = None
        self.attempted = False

    def initialize(self) -> None:
        if self.settings.enabled and not self.attempted:
            self.attempted = True
            try:
                self.client = self.factory(self.settings)
            except Exception:
                diagnostic()

    @contextmanager
    def run(self, run: UUID, conversation: UUID) -> Iterator[Observation]:
        if not self.settings.enabled or not self.settings.conversation_export_verified:
            yield NoopObservation()
            return
        self.initialize()
        if self.client is None or not trace_selected(run, self.settings.sample_rate):
            yield NoopObservation()
            return
        assert self.settings.correlation_key
        session = hmac.new(
            self.settings.correlation_key.get_secret_value().encode(),
            conversation.bytes,
            hashlib.sha256,
        ).hexdigest()
        from langfuse import propagate_attributes

        try:
            context = propagate_attributes(
                session_id=session,
                environment=self.settings.environment,
                metadata={
                    "run_id": str(run),
                    "revision": self.settings.revision,
                    **self.revisions,
                },
            )
            context.__enter__()
        except Exception:
            diagnostic()
            yield NoopObservation()
            return
        token = current_tracing.set(self)
        try:
            with self._scope("recommend-food", "chain", run=run) as observation:
                yield observation
        finally:
            current_tracing.reset(token)
            try:
                context.__exit__(None, None, None)
            except Exception:
                diagnostic()

    @contextmanager
    def observe(self, name: str, kind: str) -> Iterator[Observation]:
        with self._scope(name, kind) as observation:
            yield observation

    @contextmanager
    def _scope(
        self, name: str, kind: str, *, run: UUID | None = None
    ) -> Iterator[Observation]:
        if self.client is None or name not in NAMES or kind not in KINDS:
            yield NoopObservation()
            return
        try:
            context = self.client.start_as_current_observation(
                name=name,
                as_type=kind,
                **({"trace_context": {"trace_id": run.hex}} if run else {}),
            )
            span = context.__enter__()
        except Exception:
            diagnostic()
            yield NoopObservation()
            return
        started = time.monotonic()
        observation = SafeObservation(span)
        try:
            yield observation
        except BaseException as error:
            observation.update(
                outcome="cancelled"
                if isinstance(error, asyncio.CancelledError)
                else "failure"
            )
            raise
        finally:
            observation.update(duration_ms=(time.monotonic() - started) * 1000)
            try:
                # Never pass exceptions to SDK context managers: OTel records their text.
                context.__exit__(None, None, None)
            except Exception:
                diagnostic()

    async def close(self) -> None:
        if self.client is None:
            return
        done = threading.Event()

        def shutdown() -> None:
            try:
                self.client.shutdown()
            except Exception:
                diagnostic()
            finally:
                done.set()

        threading.Thread(
            target=shutdown, daemon=True, name="foodwise-telemetry-close"
        ).start()
        deadline = time.monotonic() + 3
        while not done.is_set() and time.monotonic() < deadline:
            await asyncio.sleep(0.01)
        if not done.is_set():
            diagnostic()
