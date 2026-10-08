"""Cloud rehearsal must preserve private references and audit only scoped data."""

import json

import httpx
import pytest
from scripts.phase11_langfuse_demo import (
    audit_scores,
    audit_usage,
    deliver_buffer,
    fetch_recent,
    private_write,
)


def test_readback_keeps_scope_and_fixed_window_across_cursor_pages():
    requests = []

    def respond(request):
        requests.append(request)
        params = request.url.params
        assert json.loads(params["filter"])[0]["value"] == ["a" * 32]
        assert params["fromStartTime"] == "start"
        assert params["toStartTime"] == "end"
        assert params["fields"] == "core,basic,io,metadata,usage,model,trace_context"
        return httpx.Response(
            200,
            json={
                "data": [{"id": str(len(requests)), "traceId": "a" * 32}],
                "meta": {"cursor": "next" if len(requests) == 1 else None},
            },
        )

    with httpx.Client(
        base_url="https://fixture.invalid", transport=httpx.MockTransport(respond)
    ) as client:
        rows = fetch_recent(client, ["a" * 32], "start", "end")
    assert len(rows) == 2
    assert requests[1].url.params["cursor"] == "next"


@pytest.mark.parametrize("identities", [[], ["not-a-trace"], ["a" * 32, "a" * 32]])
def test_readback_rejects_unscoped_or_invalid_identity_lists(identities):
    with httpx.Client(
        base_url="https://fixture.invalid",
        transport=httpx.MockTransport(lambda r: pytest.fail("Unscoped request")),
    ) as client:
        with pytest.raises(ValueError):
            fetch_recent(client, identities, "start", "end")


def test_repeated_cursor_fails_instead_of_looping():
    with httpx.Client(
        base_url="https://fixture.invalid",
        transport=httpx.MockTransport(
            lambda r: httpx.Response(200, json={"data": [], "meta": {"cursor": "same"}})
        ),
    ) as client:
        with pytest.raises(ValueError, match="cursor"):
            fetch_recent(client, ["a" * 32], "start", "end")


def test_readback_rejects_server_rows_outside_the_requested_scope():
    with httpx.Client(
        base_url="https://fixture.invalid",
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200, json={"data": [{"traceId": "b" * 32}], "meta": {}}
            )
        ),
    ) as client:
        with pytest.raises(ValueError, match="out-of-scope"):
            fetch_recent(client, ["a" * 32], "start", "end")


def test_score_audit_checks_values_duplicates_associations_and_content():
    expected = {
        "score": {
            "value": 1,
            "name": "expected_outcome",
            "trace_id": "a" * 32,
            "observation_id": "b" * 16,
            "metadata": {"denominator": 1},
        }
    }
    stored = {
        "id": "score",
        "value": 1,
        "name": "expected_outcome",
        "subject": {"id": "b" * 16, "traceId": "a" * 32},
        "metadata": {"denominator": 1},
    }
    assert audit_scores([stored], expected)["passed"]
    for rows in (
        [stored, stored],
        [{**stored, "value": 0}],
        [{**stored, "subject": {"id": "wrong"}}],
        [{**stored, "comment": "private"}],
        [{**stored, "metadata": {"unexpected": "private"}}],
    ):
        assert not audit_scores(rows, expected)["passed"]


def test_private_artifacts_have_owner_only_permissions(tmp_path):
    directory = tmp_path / "private"
    path = directory / "links.json"
    private_write(path, {"trace_links": ["opaque-private-reference"]})
    assert json.loads(path.read_text()) == {"trace_links": ["opaque-private-reference"]}
    assert path.stat().st_mode & 0o777 == 0o600
    assert directory.stat().st_mode & 0o777 == 0o700


def test_buffer_delivery_stays_bounded_and_suppresses_tombstoned_traces(tmp_path):
    from types import SimpleNamespace

    from opentelemetry.sdk.trace.export import SpanExportResult

    from food_recommender.infrastructure.telemetry.ledger import TraceLedger

    ledger = TraceLedger(tmp_path / "ledger.sqlite")
    ledger.register("live", "a" * 32)
    ledger.register("deleted", "b" * 32)
    ledger.tombstone("deleted")
    spans = [SimpleNamespace(context=SimpleNamespace(trace_id=int("a" * 32, 16)))] * 65
    spans.append(SimpleNamespace(context=SimpleNamespace(trace_id=int("b" * 32, 16))))
    received = []

    class Delivery:
        def export(self, batch):
            received.append(batch)
            return SpanExportResult.SUCCESS

    deliver_buffer(ledger, spans, Delivery())
    assert [len(batch) for batch in received] == [32, 32, 1]
    assert all(
        span.context.trace_id == int("a" * 32, 16)
        for batch in received
        for span in batch
    )


def test_cloud_usage_audit_distinguishes_reported_tokens_from_failed_attempts():
    success = {
        "type": "GENERATION",
        "model": "gpt-4o-mini",
        "metadata": {"outcome": "success"},
        "usageDetails": {"input": 10, "output": 2, "total": 12},
    }
    failed = {"type": "GENERATION", "metadata": {"outcome": "cancelled"}}
    assert audit_usage([success, failed]) == {
        "generations": 2,
        "successful_with_expected_model_and_usage": 1,
        "failed_or_cancelled_usage_not_inferred": 1,
        "passed": True,
    }
    assert not audit_usage([{**success, "usageDetails": {}}])["passed"]
