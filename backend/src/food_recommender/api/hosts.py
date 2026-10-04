"""Local HTTP host enforcement with the shared structured error envelope."""

import re

from starlette.datastructures import Headers
from starlette.types import ASGIApp, Receive, Scope, Send

from food_recommender.application.errors import ErrorCode
from food_recommender.transport.http import error_response


class LocalHosts:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http":
            host = Headers(scope=scope).get("host", "")
            matched = re.fullmatch(
                r"(?:localhost|127\.0\.0\.1|backend)(?::([0-9]{1,5}))?", host
            )
            if matched is None or (
                matched[1] is not None and not 1 <= int(matched[1]) <= 65535
            ):
                await error_response(ErrorCode.INVALID_REQUEST, status=400)(
                    scope, receive, send
                )
                return
        await self.app(scope, receive, send)
