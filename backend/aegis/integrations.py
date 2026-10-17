import asyncio
import json

import httpx

from .models import Capability, Classification, Observation, Proposal, new_id, utcnow
from .settings import Settings

MAX_RESPONSE_BYTES = 256 * 1024
REQUEST_TIMEOUT_SECONDS = 15


class Models:
    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None):
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=15, follow_redirects=False, trust_env=False)
        self.owns_client = client is None
        self.capabilities = {name: Capability() for name in ("EVREN", "LAYA")}
        self.selected_model: str | None = None

    async def request_json(self, method: str, url: str, **kwargs):
        async with asyncio.timeout(REQUEST_TIMEOUT_SECONDS):
            async with self.client.stream(method, url, **kwargs) as response:
                response.raise_for_status()
                body = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(body) + len(chunk) > MAX_RESPONSE_BYTES:
                        raise ValueError("Provider response exceeded byte limit")
                    body.extend(chunk)
                return json.loads(body)

    async def close(self):
        if self.owns_client:
            await self.client.aclose()

    async def classify(self, state: Observation, run_id: str, correlation_id: str) -> Classification:
        if self.settings.laya_url:
            try:
                headers = {}
                if self.settings.laya_token:
                    headers["Authorization"] = "Bearer " + self.settings.laya_token.get_secret_value()
                payload = await self.request_json(
                    "POST",
                    self.settings.laya_url.rstrip("/") + "/classify",
                    json={
                        "state": state.model_dump(mode="json"),
                        "run_id": run_id,
                        "correlation_id": correlation_id,
                    },
                    headers=headers,
                )
                result = Classification.model_validate(payload)
                self.capabilities["LAYA"] = Capability(
                    status="PASS",
                    checked_at=utcnow(),
                    evidence=["LAN /classify response validated", "model_version=" + result.model_version],
                )
                return result
            except Exception as exc:
                self.capabilities["LAYA"] = Capability(
                    status="FAIL",
                    checked_at=utcnow(),
                    evidence=["LAN /classify failed: " + type(exc).__name__],
                )
        return Classification(
            label="REVIEW", confidence=0, abstained=True, model_version="advisory-fallback", latency_ms=0
        )

    async def reason(
        self, state: Observation, laya: Classification, run_id: str, *, assessment: dict | None = None
    ) -> Proposal:
        if self.settings.evren_base_url and self.settings.evren_api_key:
            try:
                base = self.settings.evren_base_url.rstrip("/")
                headers = {"X-API-Key": self.settings.evren_api_key.get_secret_value()}
                status = await self.request_json("GET", base + "/terms/status", headers=headers)
                current = status.get("current_version")
                if type(current) is not int or current < 1 or status.get("accepted") is not True:
                    raise ValueError("EVREN terms acceptance missing or unrecognized status schema")
                discovery = await self.request_json("GET", base + "/models", headers=headers)
                available = [m["id"] for m in discovery["data"] if isinstance(m.get("id"), str)]
                selected = self.settings.evren_model
                if selected is None and len(available) == 1:
                    selected = available[0]
                if not selected or selected not in available:
                    raise ValueError("Select an actual discovered account model")
                self.selected_model = selected
                response = await self.request_json(
                    "POST",
                    base + "/chat/completions",
                    headers=headers,
                    json={
                        "model": selected,
                        "stream": False,
                        "max_tokens": 600,
                        "evren_tools": False,
                        "messages": [
                            {
                                "role": "system",
                                "content": (
                                    "You propose cash spot actions for a demo-only agent. You cannot execute tools or "
                                    "override policy. LAYA is operational risk, never a price oracle. Default NO_TRADE. "
                                    + (
                                        "This is an external operational risk assessment. Do not recommend investments. "
                                        "Analyze only freshness, sizing, availability and missing account context. "
                                        "Return action NO_TRADE and quantity 0; do not alter the caller's intent. "
                                        if assessment is not None
                                        else ""
                                    )
                                    + "Return ONLY a JSON object conforming to this schema: "
                                    + json.dumps(Proposal.model_json_schema())
                                ),
                            },
                            {
                                "role": "user",
                                "content": json.dumps(
                                    {
                                        "state": state.model_dump(mode="json"),
                                        "laya": laya.model_dump(mode="json"),
                                        "run_id": run_id,
                                        "max_order_quote": "25",
                                        "max_total_exposure_quote": "1000",
                                        **({"external_intent": assessment} if assessment is not None else {}),
                                    }
                                ),
                            },
                        ],
                    },
                )
                message = response["choices"][0]["message"]
                if message.get("tool_calls") or message.get("function_call"):
                    raise ValueError("Tool calls are forbidden")
                content = message["content"]
                if not isinstance(content, str) or len(content) > 8000:
                    raise ValueError("Response exceeds bounds")
                result = Proposal.model_validate_json(content)
                if assessment is not None and (result.action != "NO_TRADE" or result.quantity != 0):
                    raise ValueError("Assessment analysis cannot propose execution")
                self.capabilities["EVREN"] = Capability(
                    status="PASS",
                    checked_at=utcnow(),
                    evidence=[
                        "Authenticated /models discovery",
                        "Schema-validated proposal",
                        "model=" + selected,
                    ],
                )
                return result
            except Exception as exc:
                self.capabilities["EVREN"] = Capability(
                    status="FAIL",
                    checked_at=utcnow(),
                    evidence=["Discovery/generation failed: " + type(exc).__name__],
                )
        return Proposal(
            action="NO_TRADE",
            symbol="BTC-USDT",
            quantity="0",
            intent_id=new_id(),
            summary="EVREN unavailable or invalid; deterministic NO_TRADE fallback",
        )
