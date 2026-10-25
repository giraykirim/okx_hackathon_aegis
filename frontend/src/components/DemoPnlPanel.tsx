"use client";

import React from "react";
import type { CostGateSummary, DemoPnl } from "@/lib/types";

export type PnlSourceState = "LIVE" | "UNAVAILABLE" | "NOT_APPLICABLE";

interface DemoPnlPanelProps {
  pnl: DemoPnl | null;
  costGate: CostGateSummary | null;
  source: PnlSourceState;
}

const VALUATION_LABEL: Record<DemoPnl["valuation_status"], string> = {
  CURRENT_MARK: "Current mark",
  STALE_MARK: "Stale mark",
  NO_MARK: "No mark",
  CLOSED_NO_MARK_NEEDED: "Position closed",
  ACCOUNTING_INCOMPLETE: "Accounting incomplete",
};

function signedTone(value: string | null): string {
  if (value == null) return "text-[#9BA7B4]";
  const n = Number(value);
  return n > 0 ? "text-[#4EE1C2]" : n < 0 ? "text-[#EF4444]" : "text-[#E6EDF3]";
}

function Figure({ label, value, unit, tone }: { label: string; value: string | null; unit?: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-[#2A3542]/80 bg-[#0A0D10]/70 p-2.5">
      <div className="text-[11px] text-[#9BA7B4]">{label}</div>
      <div className={`mt-1 font-mono text-sm font-bold ${tone ?? "text-[#E6EDF3]"}`}>
        {value == null ? "unavailable" : unit ? `${value} ${unit}` : value}
      </div>
    </div>
  );
}

/** Agent-owned OKX demo PnL and pre-trade cost gate, rendered only from live backend data. */
export function DemoPnlPanel({ pnl, costGate, source }: DemoPnlPanelProps) {
  if (source === "NOT_APPLICABLE") return null;
  const latest = costGate?.latest?.assessment ?? null;
  return (
    <section aria-label="Demo PnL and cost gate" className="aegis-card rounded-xl p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[#E6EDF3]">Demo PnL · agent-owned OKX demo fills</h2>
        <span className="font-mono text-[11px] text-[#9BA7B4]" data-testid="pnl-source">
          {source === "LIVE" ? "LIVE /api/metrics/pnl" : "Backend unavailable · no PnL shown"}
        </span>
      </div>

      {source === "LIVE" && pnl == null && (
        <p className="mt-3 font-mono text-xs text-[#9BA7B4]">No verified agent-owned fills recorded.</p>
      )}

      {source === "LIVE" && pnl != null && (
        <>
          <div className="mt-3 grid grid-cols-2 gap-2.5 md:grid-cols-4">
            <Figure label="Net" value={pnl.complete ? pnl.net : null} unit="USDT" tone={signedTone(pnl.net)} />
            <Figure label="Realized" value={pnl.realized} unit="USDT" tone={signedTone(pnl.realized)} />
            <Figure label="Unrealized" value={pnl.unrealized} unit="USDT" tone={signedTone(pnl.unrealized)} />
            <Figure label="Fees (in net)" value={pnl.fees} unit="USDT eq." />
            <Figure label="Inventory" value={pnl.inventory_qty} unit="BTC" />
            <Figure label="Average cost" value={pnl.average_cost} unit="USDT" />
            <Figure label="Fills counted" value={String(pnl.fill_count)} />
            <Figure
              label="Fee currencies"
              value={
                pnl.valuation_status === "ACCOUNTING_INCOMPLETE"
                  ? null // partial sums of known fees are not shown as if complete
                  : Object.entries(pnl.fee_breakdown).map(([ccy, v]) => `${v} ${ccy}`).join(" · ") || "none"
              }
            />
          </div>
          <div className="mt-3 font-mono text-[11px] text-[#9BA7B4]" data-testid="pnl-mark">
            {VALUATION_LABEL[pnl.valuation_status]}
            {pnl.mark
              ? ` · ${pnl.mark.price} from ${pnl.mark.source} at ${pnl.mark.observed_at} (age ${Math.round(pnl.mark.age_seconds)}s)`
              : ""}
          </div>
          {!pnl.complete && (
            <div className="mt-1 font-mono text-[11px] text-[#F59E0B]" data-testid="pnl-issues">
              Net withheld: {pnl.issues.join(", ")}
            </div>
          )}
          {pnl.warnings.length > 0 && (
            <div className="mt-1 font-mono text-[10px] text-[#6E7785]">Warnings: {pnl.warnings.length}</div>
          )}
        </>
      )}

      {source === "LIVE" && costGate && (
        <div className="mt-3 border-t border-[#2A3542]/60 pt-2.5 font-mono text-[11px] text-[#9BA7B4]" data-testid="cost-gate">
          Cost gate: {costGate.evaluated_trade_proposals} proposals evaluated · {costGate.blocked_when_enforced} blocked
          {latest ? ` · latest ${latest.status}: ${latest.explanation}` : ""}
        </div>
      )}
    </section>
  );
}
