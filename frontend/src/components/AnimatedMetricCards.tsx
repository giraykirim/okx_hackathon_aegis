"use client";

import React from "react";
import { Ban, FileCheck2, Shield, ShieldCheck } from "lucide-react";
import { deriveAccurateMetrics } from "@/lib/view-helpers";
import type { Decision, Metrics } from "@/lib/types";

function useAnimatedCounter(target: number, durationMs = 420): number {
  const [value, setValue] = React.useState(target);
  const prevRef = React.useRef(target);

  React.useEffect(() => {
    const startVal = prevRef.current;
    const diff = target - startVal;
    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    const startTime = performance.now();
    let rafId = 0;

    const tick = (now: number) => {
      if (diff === 0 || prefersReducedMotion) {
        setValue(target);
        prevRef.current = target;
        return;
      }
      const elapsed = now - startTime;
      const progress = Math.min(1, elapsed / durationMs);
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(startVal + diff * eased));
      if (progress < 1) {
        rafId = requestAnimationFrame(tick);
      } else {
        prevRef.current = target;
      }
    };

    rafId = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(rafId);
  }, [target, durationMs]);

  return value;
}

interface HonestSparklineProps {
  points: number[];
  strokeColor: string;
  historyCount: number;
}

function HonestHistoryIndicator({
  points,
  strokeColor,
  historyCount,
}: HonestSparklineProps) {
  if (points.length < 3) {
    return (
      <div
        className="flex flex-col items-end justify-center text-right"
        title="Sparkline trend requires at least 3 historical decision cycles; AEGIS never fabricates synthetic chart series."
      >
        <div className="flex items-center gap-1.5 rounded-md border border-[#2A3542]/80 bg-[#0A0D10]/80 px-2 py-1">
          <span
            className="h-1.5 w-1.5 rounded-full"
            style={{ backgroundColor: strokeColor }}
          />
          <span className="font-mono text-[10px] text-[#9BA7B4]">
            {historyCount === 0
              ? "No history"
              : `${historyCount} cycle${historyCount === 1 ? "" : "s"}`}
          </span>
        </div>
        <span className="mt-1 font-mono text-[9px] text-[#6E7785]">
          Single-cycle snapshot
        </span>
      </div>
    );
  }

  const width = 96;
  const height = 30;
  const pad = 4;

  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min === 0 ? 1 : max - min;

  const coords = points.map((pt, idx) => {
    const x =
      pad + (idx / Math.max(1, points.length - 1)) * (width - pad * 2);
    const y =
      max === min
        ? height / 2
        : height - pad - ((pt - min) / range) * (height - pad * 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  });

  const linePath = `M ${coords.join(" L ")}`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="overflow-visible"
      aria-label={`Measured history across ${points.length} decisions`}
    >
      <path
        d={linePath}
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

interface AnimatedMetricCardsProps {
  metrics: Metrics | null;
  decisions?: Decision[];
  latestDecision?: Decision | null;
  eventsCount: number;
  sourceMode: string;
}

export function AnimatedMetricCards({
  metrics,
  decisions = [],
  latestDecision = null,
  eventsCount,
  sourceMode,
}: AnimatedMetricCardsProps) {
  const derived = React.useMemo(
    () => deriveAccurateMetrics(metrics, decisions, latestDecision),
    [metrics, decisions, latestDecision]
  );

  const animTotal = useAnimatedCounter(derived.totalDecisions);
  const animNoTrade = useAnimatedCounter(derived.noTradeDecisions);
  const animPolicyVeto = useAnimatedCounter(derived.policyVetoes);
  const animVerified = useAnimatedCounter(derived.verifiedExchangeOrders);

  // Build real cumulative series only when >= 3 decisions exist
  const orderedDecisions = React.useMemo(
    () => [...decisions].reverse(),
    [decisions]
  );
  const totalSeries = React.useMemo(
    () => orderedDecisions.map((_, idx) => idx + 1),
    [orderedDecisions]
  );
  const noTradeSeries = React.useMemo(
    () =>
      orderedDecisions.reduce<number[]>((acc, d) => {
        const prev = acc[acc.length - 1] ?? 0;
        return [...acc, prev + (d.proposed_action === "NO_TRADE" ? 1 : 0)];
      }, []),
    [orderedDecisions]
  );
  const vetoSeries = React.useMemo(
    () =>
      orderedDecisions.reduce<number[]>((acc, d) => {
        const prev = acc[acc.length - 1] ?? 0;
        return [
          ...acc,
          prev + (d.proposed_action !== "NO_TRADE" && !d.risk_approved ? 1 : 0),
        ];
      }, []),
    [orderedDecisions]
  );
  const verifiedSeries = React.useMemo(
    () =>
      orderedDecisions.reduce<number[]>((acc, d) => {
        const prev = acc[acc.length - 1] ?? 0;
        return [
          ...acc,
          prev +
            (d.execution_status === "VERIFIED" && d.source_mode === "OKX_DEMO"
              ? 1
              : 0),
        ];
      }, []),
    [orderedDecisions]
  );

  return (
    <section
      aria-label="Key Risk & Audit Metrics"
      className="grid grid-cols-1 gap-3.5 sm:grid-cols-2 xl:grid-cols-4"
    >
      {/* Card 1: Total Decisions */}
      <div className="aegis-card rounded-xl p-4 transition hover:border-[#4EE1C2]/35">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[#4EE1C2]/25 bg-[#4EE1C2]/10 text-[#4EE1C2]">
              <FileCheck2 className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs font-medium text-[#9BA7B4]">
                Total Decisions
              </div>
              <div className="mt-0.5 font-mono text-2xl font-bold tracking-tight text-[#E6EDF3]">
                {animTotal}
              </div>
            </div>
          </div>
          <HonestHistoryIndicator
            points={totalSeries}
            strokeColor="#4EE1C2"
            historyCount={derived.historyCount}
          />
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-[#2A3542]/60 pt-2.5 text-[11px]">
          <span className="font-mono text-[#4EE1C2]">
            {eventsCount} audit events
          </span>
          <span className="text-[#6E7785]">
            {derived.noTradeDecisions} No-Trade · {derived.policyVetoes} Vetoed
          </span>
        </div>
      </div>

      {/* Card 2: No-Trade Decisions (Voluntary NO_TRADE) */}
      <div className="aegis-card rounded-xl p-4 transition hover:border-[#F59E0B]/35">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[#F59E0B]/25 bg-[#F59E0B]/10 text-[#F59E0B]">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs font-medium text-[#9BA7B4]">
                No-Trade Decisions
              </div>
              <div className="mt-0.5 font-mono text-2xl font-bold tracking-tight text-[#E6EDF3]">
                {animNoTrade}
              </div>
            </div>
          </div>
          <HonestHistoryIndicator
            points={noTradeSeries}
            strokeColor="#F59E0B"
            historyCount={derived.historyCount}
          />
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-[#2A3542]/60 pt-2.5 text-[11px]">
          <span className="font-mono text-[#F59E0B]">
            proposed_action: NO_TRADE
          </span>
          <span className="text-[#6E7785]">Safe idle posture</span>
        </div>
      </div>

      {/* Card 3: Policy Vetoes (Blocked Trade Proposals) */}
      <div className="aegis-card rounded-xl p-4 transition hover:border-[#EF4444]/35">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[#EF4444]/25 bg-[#EF4444]/10 text-[#EF4444]">
              <Ban className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs font-medium text-[#9BA7B4]">
                Policy Vetoes
              </div>
              <div className="mt-0.5 font-mono text-2xl font-bold tracking-tight text-[#E6EDF3]">
                {animPolicyVeto}
              </div>
            </div>
          </div>
          <HonestHistoryIndicator
            points={vetoSeries}
            strokeColor="#EF4444"
            historyCount={derived.historyCount}
          />
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-[#2A3542]/60 pt-2.5 text-[11px]">
          <span className="font-mono text-[#EF4444]">
            {derived.policyVetoes === 0
              ? "0 trade proposals blocked"
              : `${derived.policyVetoes} trade proposal${
                  derived.policyVetoes === 1 ? "" : "s"
                } blocked`}
          </span>
          <span className="text-[#6E7785]">Hard Python risk gate</span>
        </div>
      </div>

      {/* Card 4: Verified Exchange & Mock Executions */}
      <div className="aegis-card rounded-xl p-4 transition hover:border-[#2A3542]">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[#2A3542] bg-[#1A222B] text-[#9BA7B4]">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs font-medium text-[#9BA7B4]">
                Verified Exchange
              </div>
              <div className="mt-0.5 font-mono text-2xl font-bold tracking-tight text-[#E6EDF3]">
                {animVerified}
              </div>
            </div>
          </div>
          <HonestHistoryIndicator
            points={verifiedSeries}
            strokeColor="#6E7785"
            historyCount={derived.historyCount}
          />
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-[#2A3542]/60 pt-2.5 text-[11px]">
          <span className="font-mono text-[#9BA7B4]">
            Mock fills: {derived.mockExecutions} · Mode: {sourceMode}
          </span>
          <span className="font-mono text-[#6E7785]">pnl: null</span>
        </div>
      </div>
    </section>
  );
}
