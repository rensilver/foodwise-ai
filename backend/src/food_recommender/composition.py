"""Process composition roots. Construction loads no models or service connections."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import async_sessionmaker

from food_recommender.application.services import Services
from food_recommender.infrastructure.config import Settings
from food_recommender.infrastructure.health import backend_readiness, local_readiness
from food_recommender.infrastructure.mcp_config import MCPSettings
from food_recommender.infrastructure.persistence import (
    PostgresUnitOfWork,
    create_database_engine,
)


@dataclass(frozen=True)
class BackendReadiness:
    settings: Settings
    probe: Callable[[Settings], Awaitable[dict[str, bool]]]

    async def check(self) -> dict[str, bool]:
        return await self.probe(self.settings)


@dataclass(frozen=True)
class MCPReadiness:
    settings: MCPSettings

    async def check(self) -> dict[str, bool]:
        return await local_readiness(
            self.settings.database_url.get_secret_value(),
            self.settings.media_root,
            writable=False,
        )


def build_backend_services(
    settings: Settings,
    *,
    probe: Callable[[Settings], Awaitable[dict[str, bool]]] = backend_readiness,
) -> Services:
    engine = create_database_engine(settings.database_url.get_secret_value())
    sessions = async_sessionmaker(engine, expire_on_commit=False)
    return Services(
        readiness=BackendReadiness(settings, probe),
        transactions=lambda: PostgresUnitOfWork(sessions),
        close=engine.dispose,
    )


def build_mcp_services(settings: MCPSettings) -> Services:
    return Services(readiness=MCPReadiness(settings))
