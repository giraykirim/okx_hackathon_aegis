"""Bounded read-only account model discovery; never accepts terms or prints a key."""

import asyncio
import json

from aegis.integrations import Models
from aegis.models import new_id
from aegis.settings import Settings


async def main():
    settings = Settings()
    if not settings.evren_base_url or not settings.evren_api_key:
        print(json.dumps({"status": "NOT_TESTED", "reason": "Set EVREN_BASE_URL and EVREN_API_KEY locally"}))
        return
    models = Models(settings)
    try:
        await models.discover_evren(new_id(), require_selection=False)
        print(
            json.dumps(
                models.safe_report(
                    {
                        "status": "PASS",
                        "available_model_ids": models.available_models,
                        "selected_model": models.selected_model,
                        "scope": "Account discovery only; native structured outputs and tool calling require separate probes",
                    }
                ),
                indent=2,
            )
        )
    except Exception as exc:
        raise SystemExit("EVREN discovery failed safely: " + type(exc).__name__) from None
    finally:
        await models.close()


if __name__ == "__main__":
    asyncio.run(main())
