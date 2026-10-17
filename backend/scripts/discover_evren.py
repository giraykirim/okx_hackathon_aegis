"""Read-only local account discovery; never accepts terms and never prints API keys."""

import asyncio
import json

import httpx

from aegis.settings import Settings


async def main():
    settings = Settings()
    if not settings.evren_api_key or not settings.evren_api_key.get_secret_value():
        raise SystemExit("Set AEGIS_EVREN_API_KEY in backend/.env locally first")
    headers = {"X-API-Key": settings.evren_api_key.get_secret_value()}
    base = settings.evren_base_url.rstrip("/")
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False, follow_redirects=False) as client:
            status = await client.get(base + "/terms/status", headers=headers)
            status.raise_for_status()
            terms = status.json()
            print(
                json.dumps(
                    {"current_version": terms.get("current_version"), "accepted": terms.get("accepted")}
                )
            )
            if terms.get("accepted") is not True:
                raise SystemExit(
                    "Review and accept the current terms in EVREN's UI before using this account"
                )
            models = await client.get(base + "/models", headers=headers)
            models.raise_for_status()
            ids = [m["id"] for m in models.json()["data"] if isinstance(m.get("id"), str)]
            print(json.dumps({"available_model_ids": ids}, indent=2))
    except Exception as exc:
        raise SystemExit("EVREN discovery failed: " + type(exc).__name__) from None


if __name__ == "__main__":
    asyncio.run(main())
