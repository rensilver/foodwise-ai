"""Bound requests before multipart/JSON parsers allocate unbounded resources."""

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from food_recommender.application.errors import ErrorCode
from food_recommender.transport.http import error_response


class BodyLimits:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["method"] not in {
            "POST",
            "PATCH",
            "DELETE",
        }:
            await self.app(scope, receive, send)
            return
        limit = (
            10 * 1024 * 1024 + 65536 if scope["path"] == "/api/v1/media" else 256 * 1024
        )
        chunks = bytearray()
        while True:
            message = await receive()
            if message["type"] == "http.disconnect":
                return
            chunks.extend(message.get("body", b""))
            if len(chunks) > limit:
                await error_response(ErrorCode.INVALID_REQUEST)(scope, receive, send)
                return
            if not message.get("more_body", False):
                break
        delivered = False

        async def bounded_receive() -> Message:
            nonlocal delivered
            if not delivered:
                delivered = True
                return {
                    "type": "http.request",
                    "body": bytes(chunks),
                    "more_body": False,
                }
            return await receive()

        await self.app(scope, bounded_receive, send)
