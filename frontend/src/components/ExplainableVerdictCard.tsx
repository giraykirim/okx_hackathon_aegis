"use client";

import React from "react";
import {
  AlertOctagon,
  CheckCircle2,
  Cpu,
  FileSearch,
  Lock,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import { explainRiskReason, formatAccountBalance } from "@/lib/view-helpers";
import type { Classification, Decision, Observation } from "@/lib/types";

interface ExplainableVerdictCardProps {
  decision: Decision | null;
  classification: Classification | null;
  observation: Observation | null;
  onInspectEvidenceId?: (id: string) => void;
}

export function ExplainableVerdictCard({
  decision,
  classification,
  observation,
  onInspectEvidenceId,
}: ExplainableVerdictCardProps) {
  const accountInfo = formatAccountBalance(observation);

  if (!decision) {
    return (
      <div className="rounded-xl border border-slate-800 bg-slate-900/60 p-5">
        <div className="flex items-center gap-2 text-slate-300">
          <ShieldAlert className="h-5 w-5 text-amber-400" />
          <h3 className="text-sm font-semibold">
            No Persisted Decision in Current Snapshot
          </h3>
        </div>
        <p className="mt-2 text-xs text-slate-400">
          The backend snapshot currently has <code className="text-slate-200">latest_decision=null</code>. Start an autonomous cycle or select a recorded scenario to inspect the explainable verdict and deterministic rule IDs.
        </p>
      </div>
    );
  }

  const isVetoed = !decision.risk_approved;
  const isMock = decision.source_mode === "MOCK";

  return (
    <section
      aria-label="Explainable Decision & Risk Verdict"
      className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg"
    >
      {/* Top Banner: Verdict + Execution Status + Source Mode */}
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-slate-800 pb-4">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            {isVetoed ? (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/50 bg-rose-500/15 px-3 py-1 font-mono text-xs font-bold text-rose-300">
                <AlertOctagon className="h-4 w-4" />
                VERDICT: VETOED / NO_TRADE ({decision.execution_status})
              </span>
            ) : (
              <span className="inline-flex items-center gap-1.5 rounded-md border border-emerald-500/50 bg-emerald-500/15 px-3 py-1 font-mono text-xs font-bold text-emerald-300">
                <CheckCircle2 className="h-4 w-4" />
                VERDICT: POLICY APPROVED ({decision.execution_status})
              </span>
            )}

            <span
              className={`rounded border px-2 py-0.5 font-mono text-xs font-semibold ${
                isMock
                  ? "border-amber-500/40 bg-amber-500/15 text-amber-300"
                  : decision.source_mode === "MARKET_ONLY"
                  ? "border-emerald-500/40 bg-emerald-500/15 text-emerald-300"
                  : "border-sky-500/40 bg-sky-500/15 text-sky-300"
              }`}
            >
              SOURCE: {decision.source_mode}
            </span>

            {decision.venue_state && (
              <span className="rounded border border-slate-700 bg-slate-800 px-2 py-0.5 font-mono text-xs text-slate-300">
                VENUE_STATE: {decision.venue_state}
              </span>
            )}
          </div>

          <h3 className="mt-2 text-base font-bold text-white">
            Explainable Risk Gate Audit — {decision.symbol} (Proposed:{" "}
            <span className="font-mono text-indigo-300">
              {decision.proposed_action} {decision.quantity} BTC
            </span>
            )
          </h3>
          <p className="mt-0.5 font-mono text-xs text-slate-400">
            Decision ID: <span className="text-slate-200">{decision.id ?? "N/A"}</span> · Run ID:{" "}
            <span className="text-slate-200">{decision.run_id}</span> · Intent ID:{" "}
            <span className="text-slate-200">{decision.intent_id}</span>
          </p>
        </div>

        <div className="flex flex-col items-end font-mono text-xs text-slate-400">
          <span>Timestamp: {decision.timestamp ?? "N/A"}</span>
          <span>
            Venue Order ID:{" "}
            <strong className="text-slate-200">
              {decision.venue_order_id ?? "null (No exchange order sent)"}
            </strong>
          </span>
          <span>
            Policy Limit Price:{" "}
            <strong className="text-slate-200">
              {decision.limit_price ? `${decision.limit_price} USDT` : "null"}
            </strong>
          </span>
        </div>
      </div>

      {/* Deterministic Rule IDs */}
      <div className="mt-4">
        <div className="flex items-center justify-between">
          <h4 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
            Deterministic Python Policy Rules ({decision.risk_reasons.length})
          </h4>
          <span className="font-mono text-[11px] text-slate-400">
            Final Execution Authority: Python Policy Engine (`backend/aegis/policy.py`)
          </span>
        </div>

        {decision.risk_reasons.length === 0 ? (
          <div className="mt-2 rounded-lg border border-emerald-500/30 bg-emerald-950/20 p-3 text-xs text-emerald-200">
            <div className="flex items-center gap-2 font-semibold">
              <ShieldCheck className="h-4 w-4 text-emerald-400" />
              All deterministic risk checks passed (`risk_reasons: []`).
            </div>
            {isMock && (
              <p className="mt-1 text-amber-300">
                Note: Because <code className="font-mono">source_mode=MOCK</code>, this cycle recorded{" "}
                <code className="font-mono">venue_state=MOCK_FILLED</code> and{" "}
                <code className="font-mono">execution_status=NOT_SENT</code>. No exchange order was sent or verified.
              </p>
            )}
          </div>
        ) : (
          <div className="mt-2 grid grid-cols-1 gap-2 md:grid-cols-2">
            {decision.risk_reasons.map((reason) => {
              const info = explainRiskReason(reason);
              return (
                <div
                  key={reason}
                  className="rounded-lg border border-rose-500/30 bg-rose-950/15 p-3"
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="rounded bg-rose-500/20 px-2 py-0.5 font-mono text-xs font-bold text-rose-300 border border-rose-500/40">
                      RULE_ID: {info.ruleId}
                    </span>
                    <span className="font-mono text-[10px] uppercase text-rose-400">
                      HARD VETO
                    </span>
                  </div>
                  <p className="mt-1.5 text-xs font-semibold text-white">
                    {info.title}
                  </p>
                  <p className="mt-0.5 text-[11px] leading-relaxed text-slate-300">
                    {info.explanation}
                  </p>
                </div>
              );
            })}
          </div>
        )}
      </div>

      {/* Three-Column Breakdown: LAYA + EVREN + Account & Market Facts */}
      <div className="mt-4 grid grid-cols-1 gap-3 lg:grid-cols-3">
        {/* Column 1: LAYA Operational Classifier */}
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3.5">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-200">
              <Cpu className="h-4 w-4 text-indigo-400" />
              LAYA Operational Classifier
            </span>
            <span
              className={`rounded px-2 py-0.5 font-mono text-[11px] font-bold ${
                decision.laya_label === "CONTINUE"
                  ? "bg-emerald-500/20 text-emerald-300"
                  : decision.laya_label === "REVIEW"
                  ? "bg-amber-500/20 text-amber-300"
                  : "bg-rose-500/20 text-rose-300"
              }`}
            >
              {decision.laya_label}
            </span>
          </div>
          <dl className="mt-2.5 space-y-1 font-mono text-xs text-slate-300">
            <div className="flex justify-between">
              <dt className="text-slate-400">Confidence:</dt>
              <dd>{(decision.laya_confidence * 100).toFixed(1)}%</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Abstained:</dt>
              <dd>{classification?.abstained ? "true (Advisory Fallback)" : "false"}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Model Version:</dt>
              <dd className="text-indigo-300">
                {classification?.model_version ?? "advisory-fallback"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Measured Latency:</dt>
              <dd>{classification?.latency_ms ?? 0} ms</dd>
            </div>
          </dl>
          <p className="mt-2 border-t border-slate-800/80 pt-2 text-[11px] text-slate-400">
            Operational regime label only. <code className="text-slate-300">CONTINUE</code> never grants order permission; LAYA is not a BTC price oracle.
          </p>
        </div>

        {/* Column 2: EVREN Bounded Reasoning */}
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3.5">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-slate-200">
              <Lock className="h-4 w-4 text-sky-400" />
              EVREN Bounded Proposal
            </span>
            <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[11px] font-semibold text-slate-200">
              {decision.proposed_action}
            </span>
          </div>
          <p className="mt-2.5 rounded bg-slate-900 p-2 font-mono text-xs text-slate-200 border border-slate-800">
            {decision.llm_summary}
          </p>
          <dl className="mt-2 space-y-1 font-mono text-xs text-slate-300">
            <div className="flex justify-between">
              <dt className="text-slate-400">Proposed Quantity:</dt>
              <dd>{decision.quantity} BTC</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Tool Invocation:</dt>
              <dd className="text-rose-300">DISABLED (Schema-Only)</dd>
            </div>
          </dl>
          <p className="mt-2 border-t border-slate-800/80 pt-2 text-[11px] text-slate-400">
            LLM proposes a typed action only; it cannot invoke arbitrary tools or override deterministic risk controls.
          </p>
        </div>

        {/* Column 3: Market & Account Provenance Truthfulness */}
        <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-3.5">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold text-slate-200">
              Market & Account Provenance
            </span>
            <span
              className={`rounded px-2 py-0.5 font-mono text-[10px] font-bold ${
                accountInfo.statusLabel === "UNAVAILABLE"
                  ? "bg-amber-500/20 text-amber-300"
                  : "bg-emerald-500/20 text-emerald-300"
              }`}
            >
              ACCOUNT: {accountInfo.statusLabel}
            </span>
          </div>
          <dl className="mt-2.5 space-y-1 font-mono text-xs text-slate-300">
            <div className="flex justify-between">
              <dt className="text-slate-400">BTC-USDT Price:</dt>
              <dd className="text-white font-semibold">
                {observation ? `${observation.price} USDT` : "UNAVAILABLE"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Bid / Ask:</dt>
              <dd>
                {observation ? `${observation.bid} / ${observation.ask}` : "N/A"}
              </dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Quote Balance:</dt>
              <dd className="text-amber-300">{accountInfo.quoteDisplay}</dd>
            </div>
            <div className="flex justify-between">
              <dt className="text-slate-400">Open Orders:</dt>
              <dd>{accountInfo.openOrdersDisplay}</dd>
            </div>
          </dl>
          <p className="mt-2 border-t border-slate-800/80 pt-2 text-[11px] text-slate-400">
            {accountInfo.note}
          </p>
        </div>
      </div>

      {/* Linked Evidence IDs */}
      <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 pt-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <span className="inline-flex items-center gap-1 text-xs font-semibold text-slate-300">
            <FileSearch className="h-3.5 w-3.5 text-indigo-400" />
            Linked Audit Evidence IDs ({decision.evidence_ids.length}):
          </span>
          {decision.evidence_ids.map((evId) => (
            <button
              key={evId}
              type="button"
              onClick={() => onInspectEvidenceId?.(evId)}
              className="rounded border border-indigo-500/30 bg-indigo-500/10 px-2 py-0.5 font-mono text-[11px] text-indigo-300 hover:bg-indigo-500/25 transition"
              title={`Click to highlight event ${evId} in timeline`}
            >
              {evId.slice(0, 12)}…
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
