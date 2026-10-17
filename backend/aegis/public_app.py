"""Restricted deployment entrypoint: public health/descriptor and authenticated assessment.

No control, private audit, wallet, exchange tool or stream route is forwarded.
The existing local/operator FastAPI app and its frozen contracts remain intact.
"""

from starlette.responses import JSONResponse

from .app import create_app
from .settings import Settings

ALLOWED = {
    ("GET", "/api/health"),
    ("GET", "/api/v1/service"),
    ("POST", "/api/v1/risk/evaluate"),
}


class PublicSurface:
    def __init__(self, inner):
        self.inner = inner

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http" and (scope["method"], scope["path"]) not in ALLOWED:
            await JSONResponse({"detail": "Not found"}, status_code=404)(scope, receive, send)
            return
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        await self.inner(scope, receive, send)


def create_public_app(settings: Settings | None = None):
    settings = settings or Settings()
    if settings.source_mode != "MARKET_ONLY" or settings.demo_enabled or settings.demo_region_confirmed:
        raise ValueError("Public service requires MARKET_ONLY and both demo execution flags disabled")
    return PublicSurface(create_app(settings))


app = create_public_app()
