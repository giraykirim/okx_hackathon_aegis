"""Restricted deployment entrypoint: public health/descriptor and authenticated assessment.

No control, private audit, wallet, exchange tool or stream route is forwarded.
The existing local/operator FastAPI app and its frozen contracts remain intact.

Optional key-less A2MCP tier: OKX.AI calls a free provider endpoint without forwarding
provider keys, so `/api/v1/a2mcp/risk/evaluate` is served only when explicitly enabled.
It reuses the same MARKET_ONLY assessment under a stricter shared per-minute bucket.
"""

import math
import time
from collections import deque

from starlette.responses import JSONResponse

from .app import create_app
from .settings import Settings

EVALUATE_PATH = "/api/v1/risk/evaluate"
A2MCP_PATH = "/api/v1/a2mcp/risk/evaluate"
ALLOWED = {
    ("GET", "/api/health"),
    ("GET", "/api/v1/service"),
    ("POST", EVALUATE_PATH),
}


class PublicSurface:
    def __init__(self, inner, settings: Settings):
        self.inner = inner
        self.settings = settings
        self.public_hits: deque[float] = deque()

    def public_tier_enabled(self) -> bool:
        key = self.settings.service_api_key
        return self.settings.service_public_tier and bool(key and key.get_secret_value())

    def admit_public(self) -> int | None:
        """Return a Retry-After value when the key-less bucket is exhausted."""
        now = time.monotonic()
        while self.public_hits and now - self.public_hits[0] >= 60:
            self.public_hits.popleft()
        if len(self.public_hits) >= self.settings.service_public_requests_per_minute:
            return max(1, math.ceil(60 - (now - self.public_hits[0])))
        self.public_hits.append(now)
        return None

    async def __call__(self, scope, receive, send):
        if scope["type"] == "websocket":
            await send({"type": "websocket.close", "code": 1008})
            return
        if scope["type"] == "http" and (scope["method"], scope["path"]) == ("POST", A2MCP_PATH):
            if not self.public_tier_enabled():
                await JSONResponse({"detail": "Not found"}, status_code=404)(scope, receive, send)
                return
            retry = self.admit_public()
            if retry is not None:
                await JSONResponse(
                    {"detail": "Public assessment rate limit reached"},
                    status_code=429,
                    headers={"Retry-After": str(retry)},
                )(scope, receive, send)
                return
            # Caller-supplied keys are ignored; the in-process credential never leaves the server.
            headers = [(k, v) for k, v in scope["headers"] if k.lower() != b"x-aegis-key"]
            headers.append((b"x-aegis-key", self.settings.service_api_key.get_secret_value().encode()))
            scope = {**scope, "path": EVALUATE_PATH, "raw_path": EVALUATE_PATH.encode(), "headers": headers}
        elif scope["type"] == "http" and (scope["method"], scope["path"]) not in ALLOWED:
            await JSONResponse({"detail": "Not found"}, status_code=404)(scope, receive, send)
            return
        await self.inner(scope, receive, send)


def create_public_app(settings: Settings | None = None):
    settings = settings or Settings()
    if settings.source_mode != "MARKET_ONLY" or settings.demo_enabled or settings.demo_region_confirmed:
        raise ValueError("Public service requires MARKET_ONLY and both demo execution flags disabled")
    return PublicSurface(create_app(settings), settings)


app = create_public_app()
