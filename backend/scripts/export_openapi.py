"""Deterministic offline API export; never reads local secrets or opens services."""

import argparse
import json
from pathlib import Path

from food_recommender.api.main import create_app
from food_recommender.application.services import Services
from food_recommender.infrastructure.config import Settings

TARGET = Path(__file__).parents[2] / "frontend/src/lib/api/openapi.json"
SCHEMA_TOKEN = "offline-schema-placeholder"


class OfflineReadiness:
    async def check(self) -> dict[str, bool]:
        raise RuntimeError("Schema export must not probe services")


def schema_text() -> str:
    # Synthetic encoding satisfies startup syntax validation only. No provider,
    # admin password or database credential is read, connected or exported.
    settings = Settings(
        GROQ_API_KEY=SCHEMA_TOKEN,
        DATABASE_URL="postgresql://offline:offline@localhost/offline",
        MCP_SERVER_URL="http://localhost:8001/mcp",
        MEDIA_ROOT=Path("/tmp/foodwise-schema"),
        ADMIN_PASSWORD_HASH="$argon2id$v=19$m=19456,t=2,p=1$"
        + "YWFhYWFhYWFhYWFhYWFhYQ$"
        + "YWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWFhYWE",
    )
    app = create_app(settings, services=Services(OfflineReadiness()))
    return json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    content = schema_text()
    if args.check:
        if not TARGET.is_file() or TARGET.read_text() != content:
            print(
                "API schema drift: run make api-schema in backend, then pnpm api:generate in frontend."
            )
            return 1
    else:
        TARGET.parent.mkdir(parents=True, exist_ok=True)
        TARGET.write_text(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
