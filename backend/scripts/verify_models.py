"""Bounded opt-in provider probes. No returned tool call is ever dispatched."""

import argparse
import asyncio
import json

from aegis.atk import ATK
from aegis.integrations import Models
from aegis.models import new_id, utcnow
from aegis.settings import ROOT, Settings


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--evren-features",
        action="store_true",
        help="Two bounded completion probes; requires account-selected model",
    )
    parser.add_argument(
        "--laya",
        action="store_true",
        help="POST configured LAN /classify using a real public ATK observation",
    )
    args = parser.parse_args()
    local = Settings()
    settings = local.model_copy(
        update={
            "source_mode": "MARKET_ONLY",
            "demo_enabled": False,
            "demo_region_confirmed": False,
            "okx_demo_api_key": None,
            "okx_demo_secret_key": None,
            "okx_demo_passphrase": None,
        }
    )
    models = Models(settings)
    run_id = new_id()
    models.begin_cycle(run_id, run_id)
    atk = ATK(settings)
    try:
        if args.evren_features:
            await models.verify_evren_features(run_id)
        if args.laya and settings.laya_url:
            atk.begin_observation(run_id)
            await models.classify(await atk.observe(), run_id, run_id)
        report = {
            "recorded_at": utcnow().isoformat(),
            "run_id": run_id,
            "configured": {
                "evren": bool(settings.evren_base_url and settings.evren_api_key),
                "evren_model_selected": bool(settings.evren_model),
                "laya": bool(settings.laya_url),
            },
            "capabilities": {k: v.model_dump(mode="json") for k, v in models.capabilities.items()},
            "model": models.selected_model,
            "laya": models.laya_metadata,
            "events": [e.model_dump(mode="json") for e in atk.tool_events() + models.tool_events()],
            "model_tools_executed": 0,
            "exchange_writes_attempted": 0,
            "scope": "Observed per-model response-format/tool-call behavior only; no tool execution or enforcement guarantee",
        }
        report = models.safe_report(report)
        (ROOT / "evidence/models.json").write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {
                    "capabilities": {k: v.status for k, v in models.capabilities.items()},
                    "model": report["model"],
                    "model_tools_executed": 0,
                }
            )
        )
        print("Evidence: backend/evidence/models.json; absent configuration is NOT_TESTED")
    finally:
        await models.close()


if __name__ == "__main__":
    asyncio.run(main())
