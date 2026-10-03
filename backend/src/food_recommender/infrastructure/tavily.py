"""Fixed Tavily endpoint with bounded response and redacted failures."""

import ipaddress
from collections.abc import Callable
from datetime import UTC, date, datetime
from email.utils import parsedate_to_datetime
from uuid import uuid4

import httpx
from pydantic import BaseModel, ConfigDict, Field, HttpUrl, SecretStr, field_validator

from food_recommender.application.ports import TrendItem
from food_recommender.application.trends import TrendProviderError


class TavilyItem(BaseModel):
    model_config = ConfigDict(extra="ignore", hide_input_in_errors=True)
    url: HttpUrl
    content: str = Field(min_length=1, max_length=20000)
    published_date: date | None = None

    @field_validator("url")
    @classmethod
    def public_url(cls, value: HttpUrl) -> HttpUrl:
        host = (value.host or "").lower().strip("[]")
        if (
            value.username
            or value.password
            or host == "localhost"
            or host.endswith((".localhost", ".local", ".internal"))
        ):
            raise ValueError("Citation URL must be public without credentials")
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            if "." not in host:
                raise ValueError("Citation URL must use a public host") from None
        else:
            if not address.is_global:
                raise ValueError("Citation URL must be public")
        return value

    @field_validator("published_date", mode="before")
    @classmethod
    def publication(cls, value: object) -> object:
        if isinstance(value, str):
            try:
                return date.fromisoformat(value[:10])
            except ValueError:
                try:
                    return parsedate_to_datetime(value).date()
                except (ValueError, TypeError):
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
        self.request_usage: list[dict[str, object]] = []

    async def search(
        self, query: str, *, max_results: int, days: int
    ) -> tuple[TrendItem, ...]:
        request_usage: dict[str, object] = {"status_code": None, "credits": None}
        self.request_usage.append(request_usage)
        self.request_usage = self.request_usage[-64:]
        try:
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
        except httpx.TimeoutException:
            raise TrendProviderError("timeout", retryable=True) from None
        except httpx.RequestError:
            raise TrendProviderError("provider_error", retryable=True) from None
        request_usage["status_code"] = response.status_code
        if response.status_code == 429 or response.status_code >= 500:
            delay = 0.0
            try:
                delay = max(0, float(response.headers.get("Retry-After", "0")))
            except ValueError:
                try:
                    delay = max(
                        0,
                        (
                            parsedate_to_datetime(response.headers["Retry-After"])
                            - self.clock()
                        ).total_seconds(),
                    )
                except (ValueError, TypeError, KeyError):
                    pass
            raise TrendProviderError(
                "rate_limited" if response.status_code == 429 else "provider_error",
                retryable=True,
                retry_after=delay,
            )
        if not response.is_success:
            raise TrendProviderError("provider_error")
        if len(response.content) > 1024 * 1024:
            raise ValueError("Provider response exceeds bounds")
        parsed = TavilyResponse.model_validate_json(response.content)
        usage = response.json().get("usage", {})
        if isinstance(usage, dict):
            credits = usage.get("credits")
            if (
                isinstance(credits, (int, float))
                and not isinstance(credits, bool)
                and 0 <= credits <= 100
            ):
                request_usage["credits"] = credits
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
