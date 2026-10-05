"""Local administrator cookies, server-side expiry/revocation and CSRF."""

from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from argon2 import PasswordHasher
from test_api_conversations import api  # noqa: F401
from test_repositories import repositories  # noqa: F401

from food_recommender.application.auth.service import AdminService
from food_recommender.infrastructure.auth import Argon2Verification
from food_recommender.infrastructure.persistence.unit_of_work import PostgresUnitOfWork


@pytest.mark.asyncio
async def test_admin_login_origin_csrf_logout_and_expiry(api, repositories):  # noqa: F811
    client, app, services = api
    factory, _ = repositories
    password = "synthetic-local-admin-password"
    hashed = PasswordHasher(memory_cost=19456, time_cost=2, parallelism=1).hash(
        password
    )
    now = [datetime(2026, 10, 4, tzinfo=UTC)]
    admin = AdminService(
        lambda: PostgresUnitOfWork(factory),
        Argon2Verification(hashed),
        clock=lambda: now[0],
    )
    app.state.services = replace(services, admin=admin)
    path = "/api/v1/admin/session"
    origin = {"origin": "http://localhost"}
    assert (await client.post(path, json={"password": password})).status_code == 403
    assert (
        await client.post(
            path,
            json={"password": password},
            headers={"origin": "https://evil.example"},
        )
    ).status_code == 403
    assert (
        await client.post(path, json={"password": "wrong"}, headers=origin)
    ).status_code == 401
    logged = await client.post(path, json={"password": password}, headers=origin)
    assert logged.status_code == 201
    assert "HttpOnly" in logged.headers["set-cookie"]
    assert "SameSite=strict" in logged.headers["set-cookie"]
    cookie = client.cookies.get("foodwise_admin")
    assert (await client.delete(path, headers=origin)).status_code == 403
    csrf = {**origin, "x-csrf-token": logged.json()["csrf_token"]}
    assert (await client.delete(path, headers=csrf)).status_code == 204
    client.cookies.set("foodwise_admin", cookie)
    assert (await client.delete(path, headers=csrf)).status_code == 401
    logged = await client.post(path, json={"password": password}, headers=origin)
    now[0] += timedelta(hours=9)
    assert (
        await client.delete(
            path, headers={**origin, "x-csrf-token": logged.json()["csrf_token"]}
        )
    ).status_code == 401
