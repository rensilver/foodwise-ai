"""HTTP scaffold health, configuration isolation and MCP discovery contracts."""

import json
import os
import unittest
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient
from test_config import environment

from food_recommender.mcp.server import create_app


class MCPScaffoldTests(unittest.TestCase):
    def test_protocol_discovers_read_only_tools(self):
        values = {name: environment()[name] for name in ("DATABASE_URL", "MEDIA_ROOT")}
        with patch.dict(os.environ, values, clear=True):
            app = create_app()
        # This is an actual HTTP ASGI transport, with the server lifespan enabled.
        with TestClient(app, base_url="http://localhost:8001") as http:
            self.assertEqual(http.get("/health/live").status_code, 200)
            with patch(
                "food_recommender.composition.local_readiness",
                AsyncMock(return_value={"database": False, "media": True}),
            ):
                response = http.get("/health/ready")
                self.assertEqual(response.status_code, 503)
                self.assertEqual(response.json()["status"], "unavailable")
            self.assertEqual(
                http.post("/mcp", headers={"Host": "evil.example"}).status_code, 400
            )
            headers = {"Accept": "application/json, text/event-stream"}
            initialized = http.post(
                "/mcp",
                headers=headers,
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-03-26",
                        "capabilities": {},
                        "clientInfo": {"name": "scaffold-test", "version": "1"},
                    },
                },
            )
            self.assertEqual(initialized.status_code, 200)
            headers["mcp-session-id"] = initialized.headers["mcp-session-id"]
            headers["mcp-protocol-version"] = "2025-03-26"
            self.assertEqual(
                http.post(
                    "/mcp",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "method": "notifications/initialized",
                    },
                ).status_code,
                202,
            )
            for method, collection in (
                ("tools/list", "tools"),
                ("resources/list", "resources"),
            ):
                response = http.post(
                    "/mcp",
                    headers=headers,
                    json={
                        "jsonrpc": "2.0",
                        "id": 2,
                        "method": method,
                    },
                )
                self.assertEqual(response.status_code, 200)
                payload = json.loads(
                    next(
                        line[6:]
                        for line in response.text.splitlines()
                        if line.startswith("data: ")
                    )
                )
                if collection == "tools":
                    self.assertEqual(
                        {t["name"] for t in payload["result"][collection]},
                        {
                            "get_restaurant_info",
                            "recommend_by_vibe",
                            "get_review",
                            "search_restaurants",
                            "search_recipes",
                            "search_images",
                            "search_food_trends",
                        },
                    )
                else:
                    self.assertEqual(len(payload["result"][collection]), 3)


if __name__ == "__main__":
    unittest.main()
