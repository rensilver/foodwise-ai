"""Offline observable health contracts for the local startup scaffolds."""

import asyncio
import tempfile
import unittest
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
from fastapi.testclient import TestClient
from food_recommender.api.main import create_app
from food_recommender.infrastructure.health import backend_readiness, local_readiness
from test_config import Settings, environment


class HealthTests(unittest.TestCase):
    def test_liveness_is_independent_and_readiness_reports_dependency_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            settings = Settings(**(environment() | {"MEDIA_ROOT": directory}))
            probe = AsyncMock(return_value={"database": False, "media": True, "mcp": False})
            with TestClient(create_app(settings, probe=probe), base_url="http://localhost") as client:
                self.assertEqual(client.get("/api/v1/health/live").status_code, 200)
                probe.assert_not_called()
                response = client.get("/api/v1/health/ready")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["dependencies"]["database"], "unavailable")
                self.assertNotIn("synthetic", response.text)

    def test_ready_requires_all_dependencies_and_rejects_unknown_hosts(self):
        probe = AsyncMock(return_value={"database": True, "media": True, "mcp": True})
        with TestClient(create_app(Settings(**environment()), probe=probe), base_url="http://localhost") as client:
            self.assertEqual(client.get("/api/v1/health/ready").status_code, 200)
            self.assertEqual(client.get("/api/v1/health/live", headers={"Host": "evil.example"}).status_code, 400)

    def test_failed_database_and_missing_media_are_not_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch("food_recommender.infrastructure.health.psycopg.AsyncConnection.connect", side_effect=RuntimeError("private-db-value")):
                result = asyncio.run(local_readiness("postgresql://synthetic", Path(directory) / "absent"))
        self.assertEqual(result, {"database": False, "media": False})

    def test_malformed_mcp_readiness_is_unavailable(self):
        client = AsyncMock()
        client.get.return_value = httpx.Response(200, json=[])
        client.__aenter__.return_value = client
        with patch("food_recommender.infrastructure.health.local_readiness", AsyncMock(return_value={"database": True, "media": True})):
            with patch("food_recommender.infrastructure.health.httpx.AsyncClient", return_value=client):
                result = asyncio.run(backend_readiness(Settings(**environment())))
        self.assertFalse(result["mcp"])


if __name__ == "__main__":
    unittest.main()
