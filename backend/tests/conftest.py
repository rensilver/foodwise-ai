"""Offline provider boundaries and opt-in disposable database fixtures."""

import ipaddress
import json
import os
import socket
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import httpx
import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict


@pytest.fixture(autouse=True)
def block_external_network(monkeypatch: pytest.MonkeyPatch) -> None:
    """Allow local integration services; block external DNS and connections."""
    resolve = socket.getaddrinfo
    connect = socket.socket.connect
    connect_ex = socket.socket.connect_ex

    def require_loopback(host: str | bytes | None) -> None:
        if host in {None, "localhost", b"localhost"}:
            return
        try:
            address = ipaddress.ip_address(
                host.decode() if isinstance(host, bytes) else host
            )
        except ValueError:
            raise RuntimeError("Tests prohibit external network access") from None
        if not address.is_loopback:
            raise RuntimeError("Tests prohibit external network access")

    def guarded_resolve(host: Any, *args: Any, **kwargs: Any) -> Any:
        require_loopback(host)
        return resolve(host, *args, **kwargs)

    def guarded_connect(sock: socket.socket, address: Any) -> None:
        if sock.family in {socket.AF_INET, socket.AF_INET6}:
            require_loopback(address[0])
        connect(sock, address)

    def guarded_connect_ex(sock: socket.socket, address: Any) -> int:
        if sock.family in {socket.AF_INET, socket.AF_INET6}:
            require_loopback(address[0])
        return connect_ex(sock, address)

    monkeypatch.setattr(socket, "getaddrinfo", guarded_resolve)
    monkeypatch.setattr(socket.socket, "connect", guarded_connect)
    monkeypatch.setattr(socket.socket, "connect_ex", guarded_connect_ex)


@pytest.fixture
def provider_transport() -> httpx.MockTransport:
    """Canned SDK responses; reject unexpected endpoints and request content."""
    directory = Path(__file__).parent / "fixtures" / "providers"

    def respond(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        if (
            request.url.host == "api.openai.com"
            and request.url.path == "/v1/chat/completions"
        ):
            assert body["model"] == "gpt-4o-mini"
            assert body["messages"] == [{"role": "user", "content": "Fixture request"}]
            name = "openai"
        elif request.url.host == "api.tavily.com" and request.url.path == "/search":
            assert body["query"] == "fixture culinary concept"
            assert body["max_results"] == 1
            name = "tavily"
        else:
            raise AssertionError("Unexpected fake-provider endpoint")
        assert request.method == "POST"
        return httpx.Response(
            200, json=json.loads((directory / f"{name}.json").read_text())
        )

    return httpx.MockTransport(respond)


@pytest.fixture
def database_url() -> str:
    dsn = os.environ.get("TEST_DATABASE_URL")
    if not dsn:
        if os.environ.get("CI") == "true":
            pytest.fail(
                "CI must configure TEST_DATABASE_URL; integration tests cannot skip"
            )
        pytest.skip(
            "Set TEST_DATABASE_URL to an initialized disposable foodwise_test database"
        )
    details = conninfo_to_dict(dsn)
    assert details.get("dbname") == "foodwise_test", (
        "Use the disposable foodwise_test database"
    )
    assert details.get("host") in {"localhost", "127.0.0.1"}, (
        "Use a localhost test database"
    )
    return dsn


@pytest.fixture
def database(database_url: str) -> Iterator[psycopg.Connection]:
    with psycopg.connect(database_url, connect_timeout=5) as connection:
        try:
            yield connection
        finally:
            # Roll back table creation and data; never commit test changes.
            connection.rollback()
