"""Fixed Tavily endpoint with bounded response and redacted failures."""

from collections.abc import Callable
from datetime import UTC, date, datetime
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, field_validator

from food_recommender.application.ports import TrendItem


class TavilyItem(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    url: HttpUrl
    content: str = Field(min_length=1, max_length=20000)
    published_date: date | None = None

    @field_validator("published_date", mode="before")
    @classmethod
    def publication(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                return None
        return value


class TavilyResponse(BaseModel):
    results: list[TavilyItem] = Field(max_length=5)


class TavilySearch:
    def __init__(
        self,
        key: SecretStr,
        client: httpx.AsyncClient,
        *,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ) -> None:
        self.key, self.client, self.clock = key, client, clock

    async def search(
        self, query: str, *, max_results: int, days: int
    ) -> tuple[TrendItem, ...]:
        response = await self.client.post(
            "https://api.tavily.com/search",
            json={
                "api_key": self.key.get_secret_value(),
                "query": query,
                "topic": "news",
                "search_depth": "basic",
                "max_results": max_results,
                "days": days,
                "include_answer": False,
                "include_raw_content": False,
                "include_usage": True,
            },
            timeout=30,
        )
        response.raise_for_status()
        if len(response.content) > 1024 * 1024:
            raise ValueError("Provider response exceeds bounds")
        parsed = TavilyResponse.model_validate_json(response.content)
        return tuple(
            TrendItem(
                uuid4(),
                str(row.url),
                row.content[:2000],
                row.published_date,
                self.clock(),
            )
            for row in parsed.results
        )
