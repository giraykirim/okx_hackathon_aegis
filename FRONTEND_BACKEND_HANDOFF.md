# AEGIS — Frontend ↔ Backend TradeCourt Council Handoff (Person 3 → Person 1 & Person 2)

## 1. Current Frontend Integration Posture
- **Zero New Backend Endpoints Invented:** The frontend consumes only the existing frozen v2 endpoints (`/api/snapshot`, `/api/events`, `/api/stream` emitting `event: aegis`).
- **Graceful Fallback Active:** While Person 1 completes the TradeCourt backend and Person 2 completes LAYA LAN integration, [`deriveTradeCourtSession`](frontend/src/lib/view-helpers.ts) automatically derives the 4-seat TradeCourt Council (`LOADING`, `UNAVAILABLE`, `SKIPPED`, `DEGRADED`, `COMPLETED`) from the existing `CLASSIFY`, `REASON`, and `RISK_GATE` events plus `Snapshot`.
- **Strictly Isolated Mock Fixture:** Visual testing of all 5 Council states uses [`MOCK_TRADE_COURT_SESSIONS`](frontend/src/lib/fixtures.ts), which is explicitly tagged `isMockFixture: true`, `sourceMode: "MOCK"`, and `MOCK COUNCIL FIXTURE — Not Real EVREN Inference`.

---

## 2. How Person 1 Can Emit Live TradeCourt Council Data (Zero Breaking Changes)

The frontend automatically detects TradeCourt Council telemetry from **either** of the following existing `/api/events` and `/api/stream` (`event: aegis`) event patterns:

### Option A (Recommended): Attach `details.council` to the existing `REASON` event
In `backend/aegis/agent.py` when emitting `"REASON"`, include an optional `council` object inside `details`:

```json
{
  "type": "REASON",
  "actor": "evren",
  "severity": "INFO",
  "message": "Typed proposal received",
  "details": {
    "action": "NO_TRADE",
    "symbol": "BTC-USDT",
    "quantity": "0",
    "intent_id": "b5ca5fa52d7a4427866dcc7f7fefa804",
    "summary": "Bounded TradeCourt consensus: NO_TRADE",
    "availability": "AVAILABLE",
    "council": {
      "session_id": "council-9d22a588",
      "state": "COMPLETED",
      "headline": "TradeCourt Multi-Seat Deliberation Completed",
      "summary": "Opportunity and Prosecutor seats evaluated BTC-USDT regime; deterministic Risk Gate holds final authority.",
      "total_deliberation_ms": 412.5,
      "is_mock": false,
      "seats": [
        {
          "seat_id": "REGIME_MAGISTRATE",
          "role_title": "1. Regime Magistrate",
          "subtitle": "LAYA Operational Regime Classifier",
          "model_name": "laya-v1-qwen-lora",
          "actor": "laya",
          "status": "COMPLETED",
          "stance": "CAUTION",
          "confidence": 0.88,
          "latency_ms": 18.4,
          "rationale": "Microstructure regime is REVIEW; spread stable but volatility elevated.",
          "flagged_rules": ["laya_not_clear"],
          "evidence_id": "3b2e5344adb14fb99e65296420e17a31",
          "is_mock": false
        },
        {
          "seat_id": "OPPORTUNITY_ADVOCATE",
          "role_title": "2. Opportunity Advocate",
          "subtitle": "EVREN Bounded Thesis & Sizing Seat",
          "model_name": "evren-discovered-model",
          "actor": "evren",
          "status": "COMPLETED",
          "stance": "ABSTAIN",
          "confidence": null,
          "latency_ms": 195.2,
          "rationale": "Abstaining from entry while LAYA posture is REVIEW.",
          "flagged_rules": ["no_trade_proposed"],
          "evidence_id": "73930514bf0f4f52b8e4a4c73e3075d3",
          "is_mock": false
        },
        {
          "seat_id": "RISK_PROSECUTOR",
          "role_title": "3. Risk Prosecutor",
          "subtitle": "Adversarial Counter-Thesis & Safety Audit Seat",
          "model_name": "evren-discovered-model",
          "actor": "evren",
          "status": "COMPLETED",
          "stance": "VETO",
          "confidence": null,
          "latency_ms": 198.9,
          "rationale": "Recommends NO_TRADE: account exposure unknown in MARKET_ONLY mode and LAYA is not CONTINUE.",
          "flagged_rules": ["unknown_account", "laya_not_clear"],
          "evidence_id": "73930514bf0f4f52b8e4a4c73e3075d3",
          "is_mock": false
        },
        {
          "seat_id": "PRESIDING_ARBITER",
          "role_title": "4. Presiding Arbiter (Risk Gate)",
          "subtitle": "Deterministic Python Execution Boundary",
          "model_name": "policy-deterministic-v2",
          "actor": "policy",
          "status": "COMPLETED",
          "stance": "VETO",
          "confidence": null,
          "latency_ms": 0.4,
          "rationale": "Deterministic Python Risk Gate enforced NO_TRADE (execution_status=NOT_SENT).",
          "flagged_rules": ["execution_disabled", "unknown_account", "laya_not_clear", "no_trade_proposed"],
          "evidence_id": "232df3a7eb714fd99072cafb5d98d172",
          "is_mock": false
        }
      ]
    }
  }
}
```

### Option B: Emit a dedicated `TRADE_COURT` or `COUNCIL` event
Alternatively, emit `self.emit("TRADE_COURT", "Council deliberation completed", actor="evren", details={ ...same council object... })`. Both `/api/events` and `/api/stream` (`event: aegis`) will pick it up immediately, and `/activity` already renders dedicated `TradeCourt Council` timeline badges for `type: "TRADE_COURT"` or `type: "COUNCIL"`.

---

## 3. Accepted Enum Values (All Optional & Case-Insensitive)

| Field | Accepted Values | Fallback if Omitted |
| :--- | :--- | :--- |
| `council.state` | `"LOADING"` \| `"UNAVAILABLE"` \| `"SKIPPED"` \| `"COMPLETED"` \| `"DEGRADED"` | Derived from `CLASSIFY` + `REASON` + `RISK_GATE` |
| `seat.seat_id` | `"REGIME_MAGISTRATE"` \| `"OPPORTUNITY_ADVOCATE"` \| `"RISK_PROSECUTOR"` \| `"PRESIDING_ARBITER"` | Mapped by seat index |
| `seat.status` | `"COMPLETED"` \| `"DEGRADED"` \| `"SKIPPED"` \| `"UNAVAILABLE"` \| `"LOADING"` \| `"MOCK_SCRIPTED"` | `"UNAVAILABLE"` (or `"MOCK_SCRIPTED"` if `source_mode == "MOCK"`) |
| `seat.stance` | `"APPROVE"` \| `"CAUTION"` \| `"VETO"` \| `"ABSTAIN"` | `"ABSTAIN"` |
| `seat.confidence` | `number` (`0.0` – `1.0`) or `null` | `null` (`"Not measured"` in UI) |
| `seat.latency_ms` | `number` (`> 0`) or `null` | `null` (`"Not measured"` in UI) |
| `seat.flagged_rules` | `string[]` (e.g. `["stale_feed", "laya_not_clear"]`) | `[]` |

---

## 4. Non-Negotiable Truthfulness Guards Enforced by Frontend
1. If `source_mode === "MOCK"`, `availability === "SCRIPTED"`, or `seat.is_mock === true`, the frontend forces `isMockFixture = true` and labels the seat `"MOCK_SCRIPTED (No External Model Call)"`.
2. If `confidence` or `latency_ms` is `null` or `0` while a seat is `UNAVAILABLE` or `MOCK_SCRIPTED`, the frontend displays `"Not measured"` instead of `0%` or `0 ms`.
3. `PRESIDING_ARBITER` (Deterministic Python Risk Gate) is always rendered as the sole `BINDING GATE` (`order_permission=false`), while AI seats are labeled `ADVISORY SEAT`.
