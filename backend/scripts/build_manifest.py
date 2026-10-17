"""Assemble evidence against the supplied 100-point rubric; never assign a jury score."""

import hashlib
import json
import xml.etree.ElementTree as ET

from aegis.models import utcnow
from aegis.settings import ROOT
from scripts.export_contract import FROZEN_V2_SHA256

REPO = ROOT.parent


def main():
    proof = json.loads((ROOT / "evidence/amendment-http.json").read_text())
    http = json.loads((ROOT / "evidence/http-smoke.json").read_text())
    mock = json.loads((ROOT / "evidence/mock-contract-http.json").read_text())
    atk = json.loads((ROOT / "evidence/atk-official.json").read_text())
    assert atk["decision"]["execution_status"] == "NOT_SENT" and atk["exchange_writes_attempted"] == 0
    assert atk["capabilities"]["ATK_MCP_CALL_TOOL"]["status"] == "PASS"
    assert all(check["status"] == "PASS" for check in mock["checks"].values())
    test_report = ET.parse(ROOT / "evidence/tests.xml").getroot()
    suites = list(test_report.iter("testsuite"))
    counts = {
        key: sum(int(s.get(key, 0)) for s in suites) for key in ("tests", "failures", "errors", "skipped")
    }
    assert counts["tests"] > 0 and counts["failures"] == counts["errors"] == 0
    assert proof["exchange_writes_attempted"] == 0
    assert http["checks"]["autonomous_http_cycle"]["status"] == "PASS"
    assert hashlib.sha256((REPO / "contracts/openapi.yaml").read_bytes()).hexdigest() == FROZEN_V2_SHA256
    receipts = [
        r
        for key in ("small_intent", "excess_notional")
        for r in proof["checks"][key]["response"]["market_provenance"]["receipts"]
    ]
    assert len(receipts) == 4 and all(r["status"] == "PASS" for r in receipts)

    def item(name, weight, status, scope, evidence):
        return {"name": name, "weight": weight, "status": status, "scope": scope, "evidence": evidence}

    rubric = [
        {
            "id": "A",
            "name": "Innovation & Real-World Value",
            "weight": 25,
            "items": [
                item(
                    "Originality",
                    10,
                    "NOT_TESTED",
                    "Novelty is for jury assessment; no independent novelty claim",
                    [],
                ),
                item(
                    "Clear problem and target user",
                    5,
                    "PASS",
                    "Written positioning, not validated customer demand",
                    ["docs/product/service.md"],
                ),
                item(
                    "Market potential / business model",
                    5,
                    "PASS",
                    "Documented price hypothesis; no billing/revenue claim",
                    ["docs/product/service.md", "backend/evidence/amendment-http.json"],
                ),
                item(
                    "Ready to go market",
                    5,
                    "NOT_TESTED",
                    "Local prototype; no public host/SLA/customer onboarding",
                    [],
                ),
            ],
        },
        {
            "id": "B",
            "name": "Agentic Design",
            "weight": 20,
            "items": [
                item(
                    "Autonomy end-to-end",
                    10,
                    "PASS",
                    "Actual autonomous MARKET_ONLY cycle with declared model fallbacks",
                    ["backend/evidence/http-smoke.json"],
                ),
                item(
                    "Reasoning and tool/API selection",
                    10,
                    "NOT_TESTED",
                    "Allowlisted multi-step tools run; real EVREN/LAYA unavailable",
                    ["backend/evidence/http-smoke.json", "backend/evidence/amendment-http.json"],
                ),
            ],
        },
        {
            "id": "C",
            "name": "Demo & Presentation",
            "weight": 20,
            "items": [
                item(
                    "Working live demo",
                    5,
                    "NOT_TESTED",
                    "Local HTTP backend demonstrated; integrated public product pending",
                    ["backend/evidence/amendment-http.json"],
                ),
                item("UX design", 5, "NOT_TESTED", "Person 3 frontend not implemented", []),
                item(
                    "Pitch quality & Q&A",
                    10,
                    "NOT_TESTED",
                    "Two-minute runbook written; presentation not rehearsed/graded",
                    ["docs/product/demo-2-minutes.md"],
                ),
            ],
        },
        {
            "id": "D",
            "name": "Technical Execution",
            "weight": 15,
            "items": [
                item(
                    "Working deployed product",
                    5,
                    "NOT_TESTED",
                    "Loopback only; public deployment not verified",
                    [],
                ),
                item(
                    "Architecture quality",
                    5,
                    "PASS",
                    "Boundaries, tests and contract compatibility verified; quality score belongs to jury",
                    [
                        "backend/evidence/tests.xml",
                        "contracts/openapi.yaml",
                        "contracts/service-openapi.yaml",
                    ],
                ),
                item(
                    "Technical difficulty",
                    5,
                    "NOT_TESTED",
                    "Real CUDA and on-chain receipt work pending other owners",
                    [],
                ),
            ],
        },
        {
            "id": "E",
            "name": "Avalanche Integration",
            "weight": 10,
            "items": [
                item(
                    "C-Chain or Avalanche L1 deployment",
                    5,
                    "NOT_TESTED",
                    "No verified deployed identity/receipt contract/runtime",
                    ["docs/product/person3-handoff.md"],
                ),
                item(
                    "Avalanche strengths",
                    5,
                    "NOT_TESTED",
                    "No measured issue-confirm-verify latency/fees; no custom L1/interchain claim",
                    [],
                ),
            ],
        },
        {
            "id": "F",
            "name": "OKX Integration",
            "weight": 10,
            "items": [
                item(
                    "Official OKX agent tooling",
                    5,
                    "PASS",
                    "Running backend executed actual pinned ATK CLI market reads",
                    ["backend/evidence/amendment-http.json", "docs/atk/evidence.md"],
                ),
                item(
                    "Could be listed on OKX.AI",
                    5,
                    "NOT_TESTED",
                    "Official requirements researched; feasibility POSSIBLE; NOT_LISTED",
                    ["docs/product/okx-ai-listing.md"],
                ),
            ],
        },
    ]
    assert sum(c["weight"] for c in rubric) == 100
    assert all(sum(i["weight"] for i in c["items"]) == c["weight"] for c in rubric)
    artifact_paths = [
        "contracts/openapi.yaml",
        "contracts/service-openapi.yaml",
        "contracts/frozen/manifest.json",
        "contracts/frozen/aegis-v2-service-1.1.0.yaml",
        "contracts/PERSON3_HANDOFF.md",
        "contracts/fixtures/risk-notional-mock.request.json",
        "contracts/fixtures/risk-notional-mock.response.json",
        "backend/evidence/mock-contract-http.json",
        "backend/evidence/mock-curl.json",
        "backend/evidence/tests.xml",
        "backend/evidence/http-smoke.json",
        "backend/evidence/amendment-http.json",
        "backend/evidence/latest.json",
        "backend/evidence/atk-official.json",
        "backend/evidence/atk-terminal.txt",
        "backend/evidence/atk-node-tests.tap",
        "docs/atk/CAPABILITIES.md",
        "docs/product/service.md",
        "docs/product/ONE_PAGER.md",
        "docs/product/demo-2-minutes.md",
        "docs/product/okx-ai-listing.md",
        "docs/product/person3-handoff.md",
        "docs/atk/evidence.md",
    ]
    artifacts = [
        {"path": p, "sha256": hashlib.sha256((REPO / p).read_bytes()).hexdigest()} for p in artifact_paths
    ]
    manifest = {
        "schema_version": "1.0.0",
        "recorded_at": utcnow().isoformat(),
        "rubric_source": {
            "authority": "User-supplied official workbook excerpt in authorized amendment",
            "workbook": "Agentic_Hackathon_Judge_Criteria.xlsx",
            "sheet": "Criteria",
            "range": "A1:F8",
            "workbook_file_independently_inspected": False,
        },
        "total_possible_points": 100,
        "self_awarded_score": None,
        "status_semantics": "PASS verifies only stated scope/evidence, not earned rubric points or production readiness",
        "ownership": {
            "person_1": ["backend/**", "contracts/**", "docs/atk/**", "docs/product/**"],
            "person_3_coordination": "Written handoff; user reports no chat and no Prompt 00 implementation",
        },
        "tests": {"status": "PASS", **counts, "timestamps": [s.get("timestamp") for s in suites]},
        "contracts": {
            "v2_status": "FROZEN_UNCHANGED",
            "v2_sha256": FROZEN_V2_SHA256,
            "additive": "contracts/service-openapi.yaml",
            "person_3_bundle": "contracts/frozen/manifest.json",
        },
        "official_atk": {
            "status": "PASS",
            "transport": "backend MCP SDK stdio client -> official MCP server; official CLI for legacy service",
            "capabilities": atk["capabilities"],
            "autonomous_run_id": atk["run_id"],
            "evidence": "backend/evidence/atk-official.json",
            "receipts": receipts,
        },
        "external_service": {
            "status": "PASS",
            "scope": "local real HTTP operational assessment only",
            "execution_authority": False,
            "public_deployment": "NOT_TESTED",
        },
        "notional_mock_service": {
            "status": "PASS",
            "source_mode": "MOCK",
            "execution_authorized": False,
            "scope": "actual HTTP/SSE, autonomous NO_TRADE/HALT, idempotent STOP and persisted correlation",
            "evidence": "backend/evidence/mock-contract-http.json",
        },
        "exchange_writes_attempted": 0,
        "live_execution": "DISABLED",
        "models": {"LAYA": "NOT_TESTED", "EVREN_AUTHENTICATED": "NOT_TESTED"},
        "avalanche": {
            "identity": "NOT_TESTED",
            "decision_receipts": "NOT_TESTED",
            "latency_ms": None,
            "fees": None,
        },
        "okx_ai": {
            "research": "VERIFIED",
            "feasibility": "POSSIBLE",
            "listing": "NOT_LISTED",
            "listing_url": None,
        },
        "immediate_blockers": [
            "No agreed public host/origin; Person 3 work not started",
            "No local EVREN key/account-discovered model",
            "No RTX LAN LAYA URL/benchmark",
            "No isolated confirmed regional demo account",
            "No verified Fuji contracts/read-back",
        ],
        "next_command": "cd backend && uv run python -m scripts.prove_mock_contract --port 8001",
        "rubric": rubric,
        "artifacts": artifacts,
    }
    path = ROOT / "evidence/jury-manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n")
    status = f"""# Current amendment status

Recorded: {manifest["recorded_at"]}

PASS: {counts["tests"]} offline tests; lint/format and contract checks are run separately. Frozen v2 is unchanged. Real local HTTP risk service, official backend ATK receipts/hashes, caller-spoof rejection, separate auth, sizing HALT, autonomous loop and SSE proof are captured. No exchange writes were attempted. Assessment does not grant order permission.

PASS: service 1.1 notional request/response, standalone deterministic MOCK HTTP/cURL, NO_TRADE/HALT phase timeline, idempotent STOP/correlation across restart and malicious-context rejection. Exact frozen Person 3 schemas, hashes and explicit fixtures are in contracts/PERSON3_HANDOFF.md. The previous quantity form remains supported.

FAIL: no unresolved failures in the referenced test report. An untested integration is not counted as passing.

NOT_TESTED: authenticated EVREN, LAN LAYA/benchmark, real OKX_DEMO execution, integrated dashboard/public backend, Fuji identity/decision receipt lifecycle and measured chain latency/fees. OKX.AI: POSSIBLE integration, NOT_LISTED. Pricing is proposed, no billing/revenue.

Immediate blocker: no agreed public host/origin and Person 3 implementation is pending. Use docs/product/person3-handoff.md; keep the backend loopback and controls private meanwhile.

Next reproducible command (local server running):

```sh
{manifest["next_command"]}
```

Evidence: backend/evidence/jury-manifest.json. This is an evidence map for the supplied 25/20/20/15/10/10 rubric, not a self-awarded score.
"""
    (REPO / "docs/product/STATUS.md").write_text(status)
    print("PASS: 100-point rubric manifest built from actual evidence; no jury score assigned")


if __name__ == "__main__":
    main()
