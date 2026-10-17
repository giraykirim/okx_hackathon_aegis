"""Explicit read-only forced-demo probe; no order submission operation is allowed."""

import asyncio
import json
from decimal import Decimal

from aegis.atk import ATK
from aegis.integrations import Models
from aegis.models import Proposal, new_id, utcnow
from aegis.policy import check
from aegis.settings import ROOT, Settings


async def main():
    persistent = Settings()
    assert persistent.okx_site == "tr"
    assert not persistent.demo_enabled and not persistent.demo_region_confirmed
    settings = persistent.model_copy(
        update={"source_mode": "OKX_DEMO", "demo_enabled": True, "demo_region_confirmed": True}
    )
    atk = ATK(settings)
    atk.begin_observation(new_id())
    original = atk.call

    async def read_only(operation, *args):
        if operation not in {"ticker", "instruments", "config", "balance", "orders"}:
            raise AssertionError("Write operation forbidden in readiness proof")
        return await original(operation, *args)

    atk.call = read_only
    models = Models(persistent)
    try:
        observation = await atk.observe()
        # The LAN advisory receives public market facts only, never private account values.
        public = observation.model_copy(
            update={
                "account_known": False,
                "account_observed_at": None,
                "quote_available": Decimal("0"),
                "base_available": Decimal("0"),
                "exposure_quote": Decimal("0"),
                "external_open_orders": False,
            }
        )
        classification = await models.classify(public, atk.run_id, atk.run_id)
        gate = check(
            observation,
            classification,
            Proposal(
                action="BUY",
                symbol="BTC-USDT",
                quantity=Decimal("0.0001"),
                intent_id=new_id(),
                summary="Read-only gate diagnostic; never submitted",
            ),
            now=utcnow(),
            source_mode="OKX_DEMO",
            approval_available=False,
            unresolved=observation.external_open_orders,
            duplicate=False,
        )
        report = {
            "recorded_at": utcnow().isoformat(),
            "evidence_kind": "REAL_FORCED_OKX_TR_DEMO_READS_NO_SUBMISSION",
            "run_id": atk.run_id,
            "site": settings.okx_site,
            "demo_profile_check": atk.capabilities["ATK_DEMO_ACCOUNT_READ"].model_dump(mode="json"),
            "account_known": observation.account_known,
            "account_values_redacted": True,
            "tool_events": [e.model_dump(mode="json") for e in atk.tool_events() + models.tool_events()],
            "laya": classification.model_dump(mode="json"),
            "gate": gate.model_dump(mode="json"),
            "approval_source": "EXPLICITLY_ABSENT_IN_READ_ONLY_PROBE",
            "order_submission": "NOT_TESTED",
            "order_reconciliation": "NOT_TESTED",
            "exchange_writes_attempted": 0,
            "persistent_demo_flags_changed": False,
        }
        (ROOT / "evidence/exchange-readiness.json").write_text(json.dumps(report, indent=2) + "\n")
        print(
            json.dumps(
                {
                    k: report[k]
                    for k in (
                        "demo_profile_check",
                        "account_known",
                        "laya",
                        "gate",
                        "order_submission",
                        "exchange_writes_attempted",
                    )
                }
            )
        )
    finally:
        await models.close()


if __name__ == "__main__":
    asyncio.run(main())
