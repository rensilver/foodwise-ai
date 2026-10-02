"""Process composition roots. Construction loads no models or service connections."""

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from food_recommender.application.services import Services
from food_recommender.infrastructure.config import Settings
from food_recommender.infrastructure.health import backend_readiness, local_readiness
from food_recommender.infrastructure.mcp_config import MCPSettings


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
    return Services(readiness=BackendReadiness(settings, probe))


def build_mcp_services(settings: MCPSettings) -> Services:
    return Services(readiness=MCPReadiness(settings))
