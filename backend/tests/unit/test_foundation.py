"""Composition, public errors and private structured logging contracts."""

import asyncio
import io
import json
import logging
from uuid import UUID

import httpx
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from test_config import Settings, environment

from food_recommender.api.dependencies import get_services
from food_recommender.api.main import create_app
from food_recommender.application.errors import ApplicationError, ErrorCode
from food_recommender.application.services import Services
from food_recommender.infrastructure.http import ObservedHTTP
from food_recommender.infrastructure.observability import (
    Runtime,
    StructuredFormatter,
    configure_logging,
    request_id,
    run_id,
)
from food_recommender.mcp.server import MCPSettings
from food_recommender.mcp.server import create_app as create_mcp_app

CANARY = "synthetic-private-profile-and-credential"
IDENTIFIER = UUID("11111111-1111-4111-8111-111111111111")


class FakeReadiness:
    def __init__(self, failure=None):
        self.calls = 0
        self.failure = failure

    async def check(self):
        self.calls += 1
        if self.failure is not None:
            raise self.failure
        return {"database": False, "media": True}


def runtime_fixture():
    stream = io.StringIO()
    logger = logging.Logger("isolated-test", logging.INFO)
    handler = logging.StreamHandler(stream)
    handler.setFormatter(StructuredFormatter())
    logger.addHandler(handler)
    ticks = iter([10.0, 10.025])
    return Runtime(
        logger=logger, clock=lambda: next(ticks), new_id=lambda: IDENTIFIER
    ), stream


def test_api_services_are_overridable_and_requests_have_safe_metrics():
    original, replacement = FakeReadiness(), FakeReadiness()
    runtime, stream = runtime_fixture()
    app = create_app(
        Settings(**environment()), services=Services(original), runtime=runtime
    )
    app.dependency_overrides[get_services] = lambda: Services(replacement)
    with TestClient(app, base_url="http://localhost") as client:
        response = client.get("/api/v1/health/ready?profile=" + CANARY)
    assert original.calls == 0 and replacement.calls == 1
    assert response.status_code == 503
    assert response.headers["x-request-id"] == str(IDENTIFIER)
    event = json.loads(stream.getvalue())
    assert event["event"] == "request_failed"
    assert event["duration_ms"] == pytest.approx(25)
    assert event["request_id"] == str(IDENTIFIER)
    assert CANARY not in stream.getvalue()
    assert request_id.get() is None


def test_liveness_uses_no_dependencies_and_factories_do_not_connect():
    probe = FakeReadiness(RuntimeError("Must not be called"))
    runtime, stream = runtime_fixture()
    app = create_app(
        Settings(**environment()), services=Services(probe), runtime=runtime
    )
    assert probe.calls == 0
    with TestClient(app, base_url="http://localhost") as client:
        response = client.get("/api/v1/health/live")
    assert probe.calls == 0
    assert response.status_code == 200
    assert json.loads(stream.getvalue())["event"] == "request_completed"


@pytest.mark.parametrize(
    "code,status,retryable",
    [
        (ErrorCode.INVALID_REQUEST, 422, False),
        (ErrorCode.NOT_FOUND, 404, False),
        (ErrorCode.CONFLICT, 409, False),
        (ErrorCode.DEPENDENCY_UNAVAILABLE, 503, True),
        (ErrorCode.INTERNAL_ERROR, 500, False),
    ],
)
def test_public_errors_are_typed_and_do_not_expose_exception_details(
    code, status, retryable
):
    runtime, stream = runtime_fixture()
    failure = ApplicationError(code)
    failure.__cause__ = RuntimeError(CANARY)
    app = create_app(
        Settings(**environment()),
        services=Services(FakeReadiness(failure)),
        runtime=runtime,
    )
    with TestClient(app, base_url="http://localhost") as client:
        response = client.get("/api/v1/health/ready", headers={"x-request-id": CANARY})
    assert response.status_code == status
    assert response.json()["error"]["code"] == code.value
    assert response.json()["error"]["retryable"] is retryable
    assert response.json()["request_id"] == str(IDENTIFIER)
    assert CANARY not in response.text + stream.getvalue()
    assert json.loads(stream.getvalue())["error_code"] == code.value


def test_unexpected_failures_are_redacted_and_mcp_uses_the_same_boundary():
    runtime, stream = runtime_fixture()
    probe = FakeReadiness(RuntimeError(CANARY))
    settings = MCPSettings(
        **{key: environment()[key] for key in ("DATABASE_URL", "MEDIA_ROOT")}
    )
    app = create_mcp_app(settings, services=Services(probe), runtime=runtime)
    with TestClient(app, base_url="http://localhost:8001") as client:
        response = client.get("/health/ready")
    assert probe.calls == 1
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert CANARY not in response.text + stream.getvalue()


def test_validation_and_http_errors_do_not_echo_inputs_or_detail():
    app = create_app(Settings(**environment()), services=Services(FakeReadiness()))

    @app.get("/test/{number}")
    async def endpoint(number: int):
        return {"number": number}

    @app.get("/private")
    async def private():
        raise HTTPException(status_code=409, detail=CANARY)

    with TestClient(app, base_url="http://localhost") as client:
        invalid = client.get("/test/" + CANARY)
        missing = client.get("/absent/" + CANARY)
        conflict = client.get("/private")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_request"
    assert missing.status_code == 404
    assert missing.json()["error"]["code"] == "not_found"
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "conflict"
    assert CANARY not in invalid.text + missing.text + conflict.text


def test_formatter_drops_arbitrary_messages_exceptions_and_untrusted_fields():
    record = logging.LogRecord(
        CANARY,
        logging.ERROR,
        CANARY,
        1,
        CANARY,
        (),
        (RuntimeError, RuntimeError(CANARY), None),
    )
    record.event = CANARY
    record.request_id = CANARY
    record.run_id = IDENTIFIER
    record.profile = {"name": CANARY}
    record.duration_ms = CANARY
    record.token_usage = 12
    record.search_calls = 2
    record.retrieval_attempts = 3
    record.stack_info = CANARY
    rendered = StructuredFormatter().format(record)
    payload = json.loads(rendered)
    assert CANARY not in rendered
    assert payload["event"] == "diagnostic"
    assert payload["run_id"] == str(IDENTIFIER)
    assert payload["token_usage"] == 12
    assert payload["search_calls"] == 2
    assert payload["retrieval_attempts"] == 3


def test_process_logging_redacts_sdk_and_server_output_without_stdout(capsys):
    stream = io.StringIO()
    for _ in range(2):
        configure_logging(stream=stream)
    try:
        raise RuntimeError(CANARY)
    except RuntimeError:
        logging.getLogger("uvicorn.error").exception(CANARY)
    logging.getLogger("httpx").info("URL: %s", CANARY)
    records = [json.loads(line) for line in stream.getvalue().splitlines()]
    assert len(records) == 2
    assert all(record["event"] == "diagnostic" for record in records)
    assert CANARY not in stream.getvalue()
    assert capsys.readouterr().out == ""


@pytest.mark.asyncio
async def test_cancellation_propagates_and_resets_context_without_response():
    runtime, stream = runtime_fixture()

    async def cancelled(scope, receive, send):
        assert request_id.get() == IDENTIFIER
        assert run_id.get() is None
        raise asyncio.CancelledError()

    async def unexpected_io(*args):
        raise AssertionError("Cancellation must not emit a response")

    run_token = run_id.set(IDENTIFIER)
    try:
        with pytest.raises(asyncio.CancelledError):
            await ObservedHTTP(cancelled, runtime=runtime)(
                {"type": "http"}, unexpected_io, unexpected_io
            )
        assert request_id.get() is None
        assert run_id.get() == IDENTIFIER
    finally:
        run_id.reset(run_token)
    event = json.loads(stream.getvalue())
    assert event["event"] == "request_cancelled"
    assert "status" not in event


@pytest.mark.asyncio
async def test_failure_after_headers_propagates_without_second_response():
    runtime, stream = runtime_fixture()
    sent = []

    async def failing_stream(scope, receive, send):
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError(CANARY)

    async def receive():
        return {"type": "http.request", "body": b""}

    async def send(message):
        sent.append(message)

    with pytest.raises(RuntimeError):
        await ObservedHTTP(failing_stream, runtime=runtime)(
            {"type": "http"}, receive, send
        )
    assert len(sent) == 1
    assert sent[0]["type"] == "http.response.start"
    assert request_id.get() is None
    event = json.loads(stream.getvalue())
    assert event["event"] == "request_failed"
    assert event["error_code"] == "internal_error"
    assert CANARY not in stream.getvalue()


@pytest.mark.asyncio
async def test_concurrent_request_context_is_isolated_and_reset():
    captured = []
    both_entered = asyncio.Event()

    class OverlappingReadiness:
        async def check(self):
            own_id = request_id.get()
            captured.append(own_id)
            if len(captured) == 2:
                both_entered.set()
            await asyncio.wait_for(both_entered.wait(), timeout=2)
            assert request_id.get() == own_id
            return {"database": True}

    app = create_app(
        Settings(**environment()), services=Services(OverlappingReadiness())
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://localhost"
    ) as client:
        responses = await asyncio.gather(
            *(client.get("/api/v1/health/ready") for _ in range(2))
        )
    assert len(set(captured)) == 2
    assert {response.headers["x-request-id"] for response in responses} == {
        str(value) for value in captured
    }
    assert request_id.get() is None
