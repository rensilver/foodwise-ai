"""Fixed public culinary resource port, independent of MCP and filesystem APIs."""

from typing import Protocol


class CatalogResources(Protocol):
    async def read(self, name: str) -> str: ...
