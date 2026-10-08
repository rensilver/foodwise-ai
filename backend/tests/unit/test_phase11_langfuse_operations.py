"""Release tracing operations preserve recommendations and private journals."""

from uuid import uuid4

import pytest
from scripts.phase10_acceptance import audit_state, load_labels
from scripts.phase10_tracing import CaptureExporter, traced_case

from food_recommender.infrastructure.telemetry.config import TelemetrySettings
from food_recommender.infrastructure.telemetry.langfuse import LazyTracing, sdk_factory


def synthetic_settings(**updates):
    return TelemetrySettings(
        LANGFUSE_ENABLED=True,
        LANGFUSE_CONVERSATION_EXPORT_VERIFIED=True,
        LANGFUSE_BASE_URL="https://us.cloud.langfuse.com",
        LANGFUSE_PUBLIC_KEY=uuid4().hex,
        LANGFUSE_SECRET_KEY="synthetic",
        LANGFUSE_CORRELATION_KEY="stable-synthetic",
        **updates,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("case", load_labels()["cases"], ids=lambda case: case["id"])
async def test_all_fixture_turns_are_identical_with_cloud_unavailable(case):
    from opentelemetry.sdk.trace.export import SpanExportResult

    class Unavailable(CaptureExporter):
        def export(self, spans):
            super().export(spans)
            return SpanExportResult.FAILURE

    exporter = Unavailable()
    disabled, _ = await traced_case(case, LazyTracing(TelemetrySettings()))
    tracing = LazyTracing(
        synthetic_settings(), factory=lambda s: sdk_factory(s, exporter)
    )
    unavailable, _ = await traced_case(case, tracing)
    tracing.client.flush()
    assert exporter.calls > 0
    for before, after in zip(disabled, unavailable, strict=True):
        assert after["final"] == before["final"]
        assert not any(audit_state(after).values())
    await tracing.close()


def test_corrupt_journal_fails_closed_before_any_sdk_export(tmp_path):
    path = tmp_path / "corrupt.sqlite"
    path.write_bytes(b"not a sqlite journal")
    calls = []
    tracing = LazyTracing(
        synthetic_settings(), ledger_path=path, factory=lambda s: calls.append(s)
    )
    with tracing.run(uuid4(), uuid4()) as observation:
        observation.update(outcome="success")
    assert not calls and tracing.client is None
    assert path.read_bytes() == b"not a sqlite journal"


def test_rotated_key_configuration_takes_effect_on_new_lifecycle():
    received = []
    for public, secret in [
        ("synthetic-old", "synthetic-old-secret"),
        ("synthetic-new", "synthetic-new-secret"),
    ]:
        settings = synthetic_settings().model_copy(
            update={
                "public_key": TelemetrySettings(LANGFUSE_PUBLIC_KEY=public).public_key,
                "secret_key": TelemetrySettings(LANGFUSE_SECRET_KEY=secret).secret_key,
            }
        )
        LazyTracing(
            settings,
            factory=lambda s: received.append(
                (s.public_key.get_secret_value(), s.secret_key.get_secret_value())
            ),
        ).initialize()
        assert secret not in repr(settings)
    assert received == [
        ("synthetic-old", "synthetic-old-secret"),
        ("synthetic-new", "synthetic-new-secret"),
    ]


def test_browser_fixture_supports_disabled_and_unavailable_sdk_modes(
    monkeypatch, tmp_path
):
    from scripts import serve_frontend_fixture

    fixture_tracing = serve_frontend_fixture.fixture_tracing
    monkeypatch.setattr(serve_frontend_fixture, "ARTIFACTS", tmp_path)

    monkeypatch.setenv("FOODWISE_TEST_TELEMETRY", "disabled")
    disabled = fixture_tracing()
    with disabled.run(uuid4(), uuid4()):
        pass
    assert disabled.client is None
    monkeypatch.setenv("FOODWISE_TEST_TELEMETRY", "unavailable")
    unavailable = fixture_tracing()
    with unavailable.run(uuid4(), uuid4()):
        pass
    unavailable.client.flush()
    assert unavailable.client is not None
    unavailable.client.shutdown()
    monkeypatch.setenv("FOODWISE_TEST_TELEMETRY", "invalid")
    with pytest.raises(ValueError):
        fixture_tracing()
