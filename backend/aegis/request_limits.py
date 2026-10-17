import asyncio

from starlette._utils import get_route_path
from starlette.responses import JSONResponse


class RiskRequestLimit:
    """Bound streamed/chunked bodies before FastAPI parses the additive assessment route."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if not (
            scope["type"] == "http"
            and scope["method"] == "POST"
            and get_route_path(scope) == "/api/v1/risk/evaluate"
        ):
            await self.app(scope, receive, send)
            return
        body = bytearray()
        try:
            async with asyncio.timeout(5):
                while True:
                    message = await receive()
                    if message["type"] == "http.disconnect":
                        return
                    chunk = message.get("body", b"")
                    if len(body) + len(chunk) > 2048:
                        await JSONResponse(
                            {"detail": "Assessment request exceeds 2048 bytes"}, status_code=413
                        )(scope, receive, send)
                        return
                    body.extend(chunk)
                    if not message.get("more_body", False):
                        break
        except TimeoutError:
            await JSONResponse({"detail": "Assessment body deadline exceeded"}, status_code=408)(
                scope, receive, send
            )
            return
        delivered = False

        async def bounded_receive():
            nonlocal delivered
            if not delivered:
                delivered = True
                return {"type": "http.request", "body": bytes(body), "more_body": False}
            return await receive()

        await self.app(scope, bounded_receive, send)
