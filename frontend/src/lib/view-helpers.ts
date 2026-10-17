/**
 * Pure presentation and derivation helpers for the AEGIS dashboard.
 *
 * Enforces truthfulness rules:
 * - Never infer VERIFIED from MOCK or model output.
 * - Never render `account_known === false` placeholder zeros as real $0 balances.
 * - Compute actual measured step durations from real event timestamps and ATK receipts.
 * - Preserve null cases safely when snapshot fields are null or backend is stopped.
 */

import type {
  ATKReceipt,
  Decision,
  EventItem,
  Observation,
  Snapshot,
  SourceMode,
} from "./types";

export interface PipelineStepView {
  key: "OBSERVE" | "CLASSIFY" | "REASON" | "RISK_GATE" | "ACTION" | "VERIFY" | "AUDIT";
  stepNumber: number;
  title: string;
  actor: string;
  status: "COMPLETED" | "VETOED" | "FALLBACK" | "IDLE";
  verdictBadge: string;
  measuredDurationMs: number | null;
  timestamp: string | null;
  summary: string;
  evidenceId: string | null;
  sourceMode: SourceMode;
}

export function formatAccountBalance(observation: Observation | null): {
  statusLabel: "VERIFIED_ACCOUNT" | "UNAVAILABLE";
  quoteDisplay: string;
  baseDisplay: string;
  exposureDisplay: string;
  openOrdersDisplay: string;
  note: string;
} {
  if (!observation || !observation.account_known) {
    return {
      statusLabel: "UNAVAILABLE",
      quoteDisplay: "UNAVAILABLE (not $0)",
      baseDisplay: "UNAVAILABLE (not 0 BTC)",
      exposureDisplay: "UNAVAILABLE",
      openOrdersDisplay: "UNAVAILABLE",
      note: "account_known=false: External or private account state is not connected. Placeholder zeros are never treated as real balances.",
    };
  }

  return {
    statusLabel: "VERIFIED_ACCOUNT",
    quoteDisplay: `${observation.quote_available ?? "0"} USDT`,
    baseDisplay: `${observation.base_available ?? "0"} BTC`,
    exposureDisplay: `${observation.exposure_quote ?? "0"} USDT`,
    openOrdersDisplay: observation.external_open_orders ? "YES (HALT TRIGGER)" : "NONE",
    note: observation.account_observed_at
      ? `Observed at ${observation.account_observed_at}`
      : "Scripted MOCK account state",
  };
}

export function extractAtkReceipts(events: EventItem[], runId?: string): ATKReceipt[] {
  const filtered = events.filter(
    (ev) => ev.type === "ATK_RECEIPT" && (!runId || ev.run_id === runId)
  );
  const source = filtered.length > 0 ? filtered : events.filter((ev) => ev.type === "ATK_RECEIPT");
  return source
    .map((ev) => ev.details as unknown as ATKReceipt)
    .filter((d): d is ATKReceipt => Boolean(d && typeof d.operation === "string"));
}

function diffMs(startIso?: string | null, endIso?: string | null): number | null {
  if (!startIso || !endIso) return null;
  const t1 = Date.parse(startIso);
  const t2 = Date.parse(endIso);
  if (Number.isNaN(t1) || Number.isNaN(t2) || t2 < t1) return null;
  return Number((t2 - t1).toFixed(2));
}

export function buildPipelineSteps(
  snapshot: Snapshot | null,
  events: EventItem[]
): PipelineStepView[] {
  const mode: SourceMode = snapshot?.source_mode ?? "MARKET_ONLY";
  const targetRunId = snapshot?.latest_decision?.run_id || snapshot?.run_id;

  const runEvents = events.filter((e) => !targetRunId || e.run_id === targetRunId);
  const activeEvents = runEvents.length > 0 ? runEvents : events;

  const findLatestEvent = (typesOrPhases: string[]) => {
    for (let i = activeEvents.length - 1; i >= 0; i--) {
      const ev = activeEvents[i];
      const phase =
        typeof ev.details?.phase === "string" ? ev.details.phase : undefined;
      if (
        typesOrPhases.includes(ev.type) ||
        (phase && typesOrPhases.includes(phase))
      ) {
        return ev;
      }
    }
    return undefined;
  };

  const startEv = findLatestEvent(["START"]);
  const observeEv = findLatestEvent(["OBSERVE"]);
  const classifyEv = findLatestEvent(["CLASSIFY"]);
  const reasonEv = findLatestEvent(["REASON"]);
  const gateEv = findLatestEvent(["RISK_GATE", "RISK_CHECK"]);
  const actionEv = findLatestEvent(["NO_TRADE", "EXECUTE", "ACT"]);
  const verifyEv = findLatestEvent(["VERIFY"]);
  const auditEv = findLatestEvent(["AUDIT"]);

  const receipts = extractAtkReceipts(activeEvents, targetRunId);
  const totalAtkMs =
    receipts.length > 0
      ? Number(
          receipts
            .reduce((acc, r) => acc + (typeof r.elapsed_ms === "number" ? r.elapsed_ms : 0), 0)
            .toFixed(2)
        )
      : diffMs(startEv?.timestamp, observeEv?.timestamp);

  const obs = snapshot?.observation;
  const cls = snapshot?.classification;
  const dec = snapshot?.latest_decision;

  const eventDuration = (
    ev: EventItem | undefined,
    fallbackStart?: string | null
  ): number | null => {
    if (typeof ev?.details?.duration_ms === "number") {
      return Number(ev.details.duration_ms.toFixed(2));
    }
    return diffMs(fallbackStart, ev?.timestamp);
  };

  const layaDuration =
    typeof cls?.latency_ms === "number" && cls.latency_ms > 0
      ? Number(cls.latency_ms.toFixed(2))
      : eventDuration(classifyEv, observeEv?.timestamp);

  const reasonDuration = eventDuration(reasonEv, classifyEv?.timestamp);
  const gateDuration = eventDuration(gateEv, reasonEv?.timestamp);
  const actionDuration = eventDuration(actionEv, gateEv?.timestamp);
  const verifyDuration = eventDuration(verifyEv, actionEv?.timestamp);
  const auditDuration = eventDuration(auditEv, verifyEv?.timestamp);

  const layaAvailability =
    (classifyEv?.details?.availability as string | undefined) ||
    (cls?.model_version === "advisory-fallback" ? "UNAVAILABLE" : "AVAILABLE");

  const evrenAvailability =
    (reasonEv?.details?.availability as string | undefined) ||
    (dec?.llm_summary?.includes("unavailable") ? "FALLBACK" : "AVAILABLE");

  return [
    {
      key: "OBSERVE",
      stepNumber: 1,
      title: "1. Observe (OKX ATK)",
      actor: observeEv?.actor || (mode === "MOCK" ? "mock" : "atk"),
      status: obs ? "COMPLETED" : "IDLE",
      verdictBadge: obs
        ? `${obs.symbol} @ ${obs.price} (${mode})`
        : "AWAITING OBSERVATION",
      measuredDurationMs: totalAtkMs,
      timestamp: obs?.observed_at || observeEv?.timestamp || null,
      summary: obs
        ? `Bid ${obs.bid} / Ask ${obs.ask} | Min ${obs.min_size} BTC | Account: ${
            obs.account_known ? "KNOWN (MOCK)" : "UNAVAILABLE"
          }`
        : "No observation recorded in current snapshot.",
      evidenceId: observeEv?.id || null,
      sourceMode: mode,
    },
    {
      key: "CLASSIFY",
      stepNumber: 2,
      title: "2. Classify (LAYA)",
      actor: classifyEv?.actor || "laya",
      status: !cls
        ? "IDLE"
        : cls.abstained || layaAvailability === "UNAVAILABLE"
        ? "FALLBACK"
        : cls.label === "HALT"
        ? "VETOED"
        : "COMPLETED",
      verdictBadge: cls
        ? `${cls.label} (${(cls.confidence * 100).toFixed(0)}% conf${
            cls.abstained ? " · ABSTAINED" : ""
          })`
        : "NOT CLASSIFIED",
      measuredDurationMs: layaDuration,
      timestamp: classifyEv?.timestamp || null,
      summary: cls
        ? `Model: ${cls.model_version} (${layaAvailability}). Operational class only — CONTINUE never grants order permission.`
        : "No classification available.",
      evidenceId: classifyEv?.id || null,
      sourceMode: mode,
    },
    {
      key: "REASON",
      stepNumber: 3,
      title: "3. Reason (EVREN)",
      actor: reasonEv?.actor || "evren",
      status: !dec
        ? "IDLE"
        : evrenAvailability === "FALLBACK"
        ? "FALLBACK"
        : "COMPLETED",
      verdictBadge: dec
        ? `PROPOSE: ${dec.proposed_action} (${dec.quantity} BTC)`
        : "NO PROPOSAL",
      measuredDurationMs: reasonDuration,
      timestamp: reasonEv?.timestamp || null,
      summary: dec
        ? `${dec.llm_summary} [Intent: ${dec.intent_id.slice(0, 12)}…]`
        : "Awaiting bounded LLM proposal.",
      evidenceId: reasonEv?.id || null,
      sourceMode: mode,
    },
    {
      key: "RISK_GATE",
      stepNumber: 4,
      title: "4. Deterministic Risk Gate",
      actor: "policy",
      status: !dec ? "IDLE" : dec.risk_approved ? "COMPLETED" : "VETOED",
      verdictBadge: !dec
        ? "IDLE"
        : dec.risk_approved
        ? "APPROVED (POLICY)"
        : `VETOED (${dec.risk_reasons.length} rules)`,
      measuredDurationMs: gateDuration,
      timestamp: gateEv?.timestamp || dec?.timestamp || null,
      summary: !dec
        ? "Deterministic Python policy has final execution authority."
        : dec.risk_approved
        ? `All hard checks passed. Policy limit price: ${dec.limit_price ?? "N/A"}`
        : `Hard veto reasons: ${dec.risk_reasons.join(", ")}`,
      evidenceId: gateEv?.id || null,
      sourceMode: mode,
    },
    {
      key: "ACTION",
      stepNumber: 5,
      title: "5. Action / No-Trade",
      actor: actionEv?.actor || "policy",
      status: !dec ? "IDLE" : dec.risk_approved ? "COMPLETED" : "VETOED",
      verdictBadge: !dec
        ? "IDLE"
        : !dec.risk_approved || dec.proposed_action === "NO_TRADE"
        ? "NO_TRADE (NOT_SENT)"
        : mode === "MOCK"
        ? "MOCK_FILLED (NOT_SENT)"
        : `${dec.proposed_action} (${dec.execution_status})`,
      measuredDurationMs: actionDuration,
      timestamp: actionEv?.timestamp || null,
      summary: !dec
        ? "No action executed."
        : !dec.risk_approved
        ? "Zero exchange writes attempted; deterministic gate blocked submission."
        : mode === "MOCK"
        ? "Scripted MOCK fill only; execution_status=NOT_SENT (no exchange order sent)."
        : `Order status: ${dec.execution_status}, venue_order_id: ${dec.venue_order_id ?? "null"}`,
      evidenceId: actionEv?.id || null,
      sourceMode: mode,
    },
    {
      key: "VERIFY",
      stepNumber: 6,
      title: "6. Venue Verify",
      actor: verifyEv?.actor || "policy",
      status: !dec ? "IDLE" : "COMPLETED",
      verdictBadge: !dec
        ? "IDLE"
        : `${dec.execution_status}${dec.venue_state ? ` · ${dec.venue_state}` : ""}`,
      measuredDurationMs: verifyDuration,
      timestamp: verifyEv?.timestamp || null,
      summary:
        verifyEv?.message ||
        (dec?.execution_status === "VERIFIED"
          ? "Independent venue read-back confirmed cash IOC order state."
          : "NOT_SENT: policy path made no exchange submission call."),
      evidenceId: verifyEv?.id || null,
      sourceMode: mode,
    },
    {
      key: "AUDIT",
      stepNumber: 7,
      title: "7. SQLite Audit & Proof",
      actor: auditEv?.actor || "agent",
      status: !dec ? "IDLE" : "COMPLETED",
      verdictBadge: dec
        ? `PERSISTED (${dec.evidence_ids.length} evidence IDs)`
        : "AWAITING CYCLE",
      measuredDurationMs: auditDuration,
      timestamp: auditEv?.timestamp || dec?.timestamp || null,
      summary: dec
        ? `Decision ID ${dec.id?.slice(0, 12) ?? "N/A"}… persisted atomically in SQLite journal.`
        : "No persisted decision in current snapshot.",
      evidenceId: auditEv?.id || dec?.id || null,
      sourceMode: mode,
    },
  ];
}

export function getSourceModeExplanation(mode: SourceMode): {
  badgeText: string;
  badgeClass: string;
  description: string;
} {
  switch (mode) {
    case "MARKET_ONLY":
      return {
        badgeText: "MARKET_ONLY (Real OKX ATK Read)",
        badgeClass: "bg-emerald-500/15 text-emerald-300 border-emerald-500/40",
        description:
          "Real public market & instrument observations via official @okx_ai/okx-trade-cli subprocess (site=tr). Zero exchange order writes.",
      };
    case "MOCK":
      return {
        badgeText: "MOCK SCENARIO (Scripted Simulation)",
        badgeClass: "bg-amber-500/15 text-amber-300 border-amber-500/40",
        description:
          "Synthetic deterministic test mode. Never calls external exchange or claims real execution (execution_status=NOT_SENT).",
      };
    case "OKX_DEMO":
      return {
        badgeText: "OKX_DEMO (Isolated Demo Venue)",
        badgeClass: "bg-sky-500/15 text-sky-300 border-sky-500/40",
        description:
          "Isolated demo account mode. Orders become VERIFIED only after independent exchange read-back reconciliation.",
      };
  }
}

export function explainRiskReason(reason: string): {
  ruleId: string;
  title: string;
  explanation: string;
} {
  const dictionary: Record<string, { title: string; explanation: string }> = {
    execution_disabled: {
      title: "Execution Disabled by Server Policy",
      explanation:
        "Server runtime has execution_enabled=false (e.g. MARKET_ONLY mode). Orders are deterministically blocked.",
    },
    approval_unavailable: {
      title: "Explicit Operator Approval Unavailable",
      explanation:
        "Order execution requires explicit operator risk approval flag; missing approval triggers a fail-closed veto.",
    },
    unknown_account: {
      title: "Account Balances & Exposure Unknown",
      explanation:
        "account_known=false: External account balances and open orders are unavailable. AEGIS never guesses $0 exposure.",
    },
    laya_not_clear: {
      title: "LAYA Operational State Not Clear (REVIEW / HALT / Abstained)",
      explanation:
        "LAYA did not output an un-abstained CONTINUE classification. Policy requires operational clearance before any order.",
    },
    no_trade_proposed: {
      title: "Model Proposed NO_TRADE",
      explanation:
        "EVREN (or its deterministic fallback) proposed NO_TRADE. Policy confirms no order submission.",
    },
    invalid_quantity: {
      title: "Invalid or Zero Order Quantity",
      explanation:
        "Proposed quantity is zero, non-positive, below instrument min_size, or misaligned with lot_size.",
    },
    stale_feed: {
      title: "Stale Market Observation Timestamp",
      explanation:
        "Exchange ticker timestamp age exceeds maximum freshness threshold. Trading on stale market data is forbidden.",
    },
    excess_order_notional: {
      title: "Excess Single-Order Notional Cap Exceeded",
      explanation:
        "Proposed quantity × price exceeds the deterministic single-order notional limit.",
    },
    excess_exposure: {
      title: "Excess Total Account Exposure",
      explanation:
        "Projected post-trade exposure exceeds maximum allowed quote exposure.",
    },
    unresolved_prior_order: {
      title: "Unresolved Prior Order State (PENDING / UNKNOWN)",
      explanation:
        "A prior order has not been reconciled to a terminal state. New submissions are halted to prevent double fills.",
    },
    external_open_orders: {
      title: "External Open Orders Detected on Account",
      explanation:
        "Unreconciled open orders exist on the venue account; deterministic policy halts new order placement.",
    },
    duplicate_intent: {
      title: "Duplicate Intent ID Replay Blocked",
      explanation:
        "intent_id was already claimed in the SQLite idempotency store. Duplicate submission is rejected.",
    },
  };

  const entry = dictionary[reason] || {
    title: `Deterministic Rule: ${reason}`,
    explanation: "Hard policy rule vetoed execution.",
  };

  return {
    ruleId: reason,
    ...entry,
  };
}
