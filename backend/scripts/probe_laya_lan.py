"""Explicit LAN-only schema probe with synthetic inputs; no keys or execution."""

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from aegis.models import Classification

base = "http://192.168.2.60:8770"
facts = dict(
    symbol="BTC-USDT",
    site="tr",
    source_mode="MARKET_ONLY",
    feed_age_seconds=0,
    intent_requested=False,
    quantity="0",
    account_known=False,
    approval_available=False,
    api_timeout=False,
    agents_disagree=False,
    unknown_order=False,
    duplicate_intent=False,
    permission_revoked=False,
    injection_detected=False,
    deployment_integrity_failure=False,
    excess_exposure=False,
)
obs = dict(
    symbol="BTC-USDT",
    observed_at=datetime.now(timezone.utc).isoformat(),
    price="50000",
    ask="50001",
    bid="49999",
    min_size="0.00001",
    lot_size="0.00000001",
    tick_size="0.1",
    instrument_live=True,
    account_known=False,
    exposure_quote="0",
    quote_available="0",
    base_available="0",
    account_observed_at=None,
    external_open_orders=False,
)
results = []
for name, path, state in [
    ("health", "/healthz", None),
    ("legacy_observation", "/classify", obs),
    ("unsupported", "/classify", {"unsupported": True}),
    ("candidate_operational_NOT_YET_COORDINATED", "/classify", {"operational": facts}),
    ("candidate_unknown_permission", "/classify", {"operational": {**facts, "permission_revoked": None}}),
]:
    body = (
        None
        if state is None
        else {"state": state, "run_id": "LAN_CONTRACT_PROBE", "correlation_id": "LAN_CONTRACT_PROBE"}
    )
    req = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    t = time.monotonic()
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req, timeout=5) as r:
            raw = r.read(16385)
            if len(raw) > 16384:
                raise ValueError("Response size limit")
            data = json.loads(raw)
            status = r.status
        typed_valid = None
        if state is not None:
            Classification.model_validate(data)
            typed_valid = True
        exact = (
            None
            if state is None
            else set(data) == {"label", "confidence", "abstained", "model_version", "latency_ms"}
        )
        results.append(
            dict(
                scenario=name,
                input_source="SYNTHETIC_CONTRACT_FIXTURE" if body else "REAL_LAN_HEALTH",
                request=body,
                response=data,
                http_status=status,
                wall_latency_ms=round((time.monotonic() - t) * 1000, 3),
                exact_five_response_fields=exact,
                typed_response_valid=typed_valid,
                expected_model_version_matches=data.get("model_version") == "aegis-laya-base-f38a07fa01db",
            )
        )
    except Exception as e:
        results.append(dict(scenario=name, error_type=type(e).__name__))
doc = {
    "evidence_kind": "REAL_LAN_CONTRACT_TEST",
    "checked_at": datetime.now(timezone.utc).isoformat(),
    "service_origin": base,
    "execution_attempts": 0,
    "independent_model_success_proven": False,
    "cases": results,
}
Path("/tmp/aegis-laya-lan.json").write_text(json.dumps(doc, indent=2) + "\n")
print(json.dumps([{k: v for k, v in c.items() if k != "request"} for c in results], indent=2))
if any(
    "error_type" in case
    or case.get("exact_five_response_fields") is False
    or not case.get("expected_model_version_matches")
    for case in results
):
    raise SystemExit(1)
