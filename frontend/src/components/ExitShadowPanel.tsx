"use client";

import React from "react";
import type { ExitShadowRead } from "@/lib/types";

export type ExitShadowSourceState = "LIVE" | "UNAVAILABLE" | "DISCONNECTED" | "NOT_APPLICABLE";

interface ExitShadowPanelProps {
  data: ExitShadowRead | null;
  source: ExitShadowSourceState;
  /** Client clock (ms) when `data` arrived; the record keeps ageing from here until a new answer. */
  receivedAt: number | null;
}

const SOURCE_LABEL: Record<Exclude<ExitShadowSourceState, "NOT_APPLICABLE">, string> = {
  LIVE: "LIVE /api/metrics/exit-shadow",
  UNAVAILABLE: "Backend unavailable · no exit assessment shown",
  DISCONNECTED: "Connection lost · no exit assessment shown",
};

const STATE_LABEL: Record<ExitShadowRead["state"], string> = {
  NO_ASSESSMENT: "No assessment",
  CURRENT: "Current",
  STALE: "STALE — not current",
  SUPERSEDED: "SUPERSEDED — owned inventory changed since this assessment",
};

/** Wall clock ticking once a second, so ages advance even when no new response arrives. */
function useNow(): number | null {
  const [now, setNow] = React.useState<number | null>(null);
  React.useEffect(() => {
    const tick = () => setNow(Date.now());
    const first = setTimeout(tick, 0);
    const timer = setInterval(tick, 1000);
    return () => {
      clearTimeout(first);
      clearInterval(timer);
    };
  }, []);
  return now;
}

function Figure({ label, value, unit }: { label: string; value: string | null; unit?: string }) {
  return (
    <div className="rounded-lg border border-[#2A3542]/80 bg-[#0A0D10]/70 p-2.5">
      <div className="text-[11px] text-[#9BA7B4]">{label}</div>
      <div className="mt-1 font-mono text-sm font-bold text-[#E6EDF3]">
        {value == null ? "unavailable" : unit ? `${value} ${unit}` : value}
      </div>
    </div>
  );
}

/**
 * Persisted SHADOW exit assessment of the agent's verified owned inventory. Read-only: the
 * figure is full-close capacity after lot/minimum limits, never an order or a sell signal.
 * Quantities are shown only while the record is current by the backend's verdict *and* by the
 * client clock since it arrived; stale, superseded or unreachable records withhold the numbers.
 */
export function ExitShadowPanel({ data, source, receivedAt }: ExitShadowPanelProps) {
  const now = useNow();
  if (source === "NOT_APPLICABLE") return null;
  const live = source === "LIVE" ? data : null;
  const record = live?.assessment ?? null;
  const proposal = record?.proposal ?? null;
  // Elapsed since the answer arrived; the backend's ages were measured at its read time.
  const elapsed = now != null && receivedAt != null ? Math.max(0, (now - receivedAt) / 1000) : 0;
  const age = live?.age_seconds != null ? live.age_seconds + elapsed : null;
  const marketAge = live?.market_age_seconds != null ? live.market_age_seconds + elapsed : null;
  const aged: string[] = [];
  if (live?.current) {
    if (age == null || age > live.max_age_seconds) aged.push("assessment_stale");
    if (
      live.market_dependent &&
      (marketAge == null || live.market_max_age_seconds == null || marketAge > live.market_max_age_seconds)
    ) {
      aged.push("market_data_expired");
    }
  }
  const current = live?.current === true && aged.length === 0;
  const state = live ? (live.state === "CURRENT" && !current ? "STALE" : live.state) : null;
  const reasons = Array.from(new Set([...(live?.not_current_reasons ?? []), ...aged]));
  const verifiedZero =
    proposal?.status === "NO_EXIT" &&
    proposal.reasons.includes("no_owned_inventory") &&
    proposal.owned_net_btc === "0.00000000";
  return (
    <section aria-label="Shadow exit assessment" className="aegis-card rounded-xl p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="text-sm font-semibold text-[#E6EDF3]">Exit capacity · agent-owned inventory</h2>
        <span
          className="rounded border border-[#F59E0B]/60 px-2 py-0.5 font-mono text-[11px] font-bold text-[#F59E0B]"
          data-testid="exit-shadow-banner"
        >
          SHADOW — emir gönderilmez · no order is sent
        </span>
      </div>
      <div className="mt-1 font-mono text-[11px] text-[#9BA7B4]" data-testid="exit-shadow-source">
        {SOURCE_LABEL[source]}
      </div>

      {live?.state === "NO_ASSESSMENT" && (
        <p className="mt-3 font-mono text-xs text-[#9BA7B4]">No shadow exit assessment recorded yet.</p>
      )}

      {live && state && record && proposal && (
        <>
          <div
            className={`mt-3 font-mono text-xs font-bold ${current ? "text-[#E6EDF3]" : "text-[#F59E0B]"}`}
            data-testid="exit-shadow-status"
          >
            {current ? proposal.status : `Last recorded ${proposal.status} (not current)`}
          </div>
          <div className="mt-1 font-mono text-[11px] text-[#9BA7B4]" data-testid="exit-shadow-freshness">
            {STATE_LABEL[state]} · assessed {record.computed_at}
            {age != null ? ` (age ${Math.round(age)}s, max ${live.max_age_seconds}s)` : ""}
            {` · ${record.source_mode}`}
            {marketAge != null && live.market_max_age_seconds != null
              ? ` · market ${Math.round(marketAge)}s/${live.market_max_age_seconds}s`
              : ""}
            {reasons.length > 0 ? ` · ${reasons.join(", ")}` : ""}
          </div>
          {current ? (
            <div className="mt-3 grid grid-cols-2 gap-2.5 md:grid-cols-4">
              <Figure label="Owned net inventory" value={proposal.owned_net_btc} unit="BTC" />
              <Figure label="Close capacity after lot/min" value={proposal.proposed_sell_btc} unit="BTC" />
              <Figure label="Remaining / dust" value={proposal.remaining_btc} unit="BTC" />
              <Figure
                label="Lot / min size"
                value={proposal.lot_size && proposal.min_size ? `${proposal.lot_size} / ${proposal.min_size}` : null}
              />
            </div>
          ) : (
            <p className="mt-3 font-mono text-xs text-[#9BA7B4]" data-testid="exit-shadow-withheld">
              Quantities withheld: this record is not current.
            </p>
          )}
          {current && verifiedZero && (
            <div className="mt-2 font-mono text-[11px] text-[#9BA7B4]" data-testid="exit-shadow-zero">
              Verified zero owned inventory ({record.inventory_basis.owned_fill_count} owned fills replayed).
            </div>
          )}
          <div className="mt-2 font-mono text-[11px] text-[#9BA7B4]" data-testid="exit-shadow-reasons">
            Blocking reasons: {proposal.reasons.length > 0 ? proposal.reasons.join(", ") : "none"}
          </div>
          <div className="mt-1 font-mono text-[10px] text-[#6E7785]">
            Full-close capacity (fraction {proposal.requested_fraction}) — not a sell signal. Only verified agent fills
            count; preloaded account BTC is excluded ({record.inventory_basis.excluded_unowned_fills} unowned fills
            ignored). Not executable; no order adapter.
          </div>
        </>
      )}
    </section>
  );
}
