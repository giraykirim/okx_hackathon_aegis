"use client";

import React from "react";
import { Code2, FileCheck2, Shield, ShieldCheck } from "lucide-react";
import type { Metrics } from "@/lib/types";

function useAnimatedCounter(target: number, durationMs = 680): number {
  const [value, setValue] = React.useState(target);
  const prevRef = React.useRef(target);

  React.useEffect(() => {
    const startVal = prevRef.current;
    const diff = target - startVal;
    if (diff === 0) {
      setValue(target);
      return;
    }

    const startTime = performance.now();
    let rafId = 0;

    const tick = (now: number) => {
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

interface SparklineProps {
  points: number[];
  strokeColor: string;
  fillId: string;
}

function AnimatedSparkline({ points, strokeColor, fillId }: SparklineProps) {
  const width = 104;
  const height = 34;
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
  const areaPath = `${linePath} L ${width - pad},${height} L ${pad},${height} Z`;

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className="overflow-visible"
      aria-hidden="true"
    >
      <defs>
        <linearGradient id={fillId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={strokeColor} stopOpacity="0.28" />
          <stop offset="100%" stopColor={strokeColor} stopOpacity="0.0" />
        </linearGradient>
      </defs>
      <path d={areaPath} fill={`url(#${fillId})`} />
      <path
        key={points.join(",")}
        d={linePath}
        fill="none"
        stroke={strokeColor}
        strokeWidth="1.75"
        strokeLinecap="round"
        strokeLinejoin="round"
        className="animate-draw-line"
      />
    </svg>
  );
}

interface AnimatedMetricCardsProps {
  metrics: Metrics | null;
  eventsCount: number;
  sourceMode: string;
}

export function AnimatedMetricCards({
  metrics,
  eventsCount,
  sourceMode,
}: AnimatedMetricCardsProps) {
  const totalDecisions = metrics?.decisions ?? 1;
  const policyVetoed = metrics?.vetoed ?? 1;
  const verifiedExchange = metrics?.verified_exchange_orders ?? 0;
  const mockExecutions = metrics?.mock_executions ?? 0;

  const animDecisions = useAnimatedCounter(totalDecisions);
  const animVetoed = useAnimatedCounter(policyVetoed);
  const animVerified = useAnimatedCounter(verifiedExchange);
  const animMock = useAnimatedCounter(mockExecutions);

  const vetoRate =
    totalDecisions > 0 ? Math.round((policyVetoed / totalDecisions) * 100) : 100;

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
                Decisions Evaluated
              </div>
              <div className="mt-0.5 font-mono text-2xl font-bold tracking-tight text-[#E6EDF3]">
                {animDecisions}
              </div>
            </div>
          </div>
          <AnimatedSparkline
            points={[1, 2, 2, 3, 4, 3, 5, Math.max(2, totalDecisions + 3)]}
            strokeColor="#4EE1C2"
            fillId="spark-decisions"
          />
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-[#2A3542]/60 pt-2.5 text-[11px]">
          <span className="font-mono text-[#4EE1C2]">
            {eventsCount} audit events
          </span>
          <span className="text-[#6E7785]">Persisted in SQLite</span>
        </div>
      </div>

      {/* Card 2: Policy Vetoed */}
      <div className="aegis-card rounded-xl p-4 transition hover:border-[#F59E0B]/35">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[#F59E0B]/25 bg-[#F59E0B]/10 text-[#F59E0B]">
              <Shield className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs font-medium text-[#9BA7B4]">
                Policy Vetoed
              </div>
              <div className="mt-0.5 font-mono text-2xl font-bold tracking-tight text-[#E6EDF3]">
                {animVetoed}
              </div>
            </div>
          </div>
          <AnimatedSparkline
            points={[2, 3, 3, 4, 3, 5, 4, Math.max(2, policyVetoed + 3)]}
            strokeColor="#F59E0B"
            fillId="spark-vetoed"
          />
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-[#2A3542]/60 pt-2.5 text-[11px]">
          <span className="font-mono text-[#F59E0B]">
            {vetoRate}% of decisions
          </span>
          <span className="text-[#6E7785]">Deterministic safety gate</span>
        </div>
      </div>

      {/* Card 3: Verified Exchange */}
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
          <AnimatedSparkline
            points={[0, 0, 0, 0, 0, 0, 0, verifiedExchange]}
            strokeColor="#6E7785"
            fillId="spark-verified"
          />
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-[#2A3542]/60 pt-2.5 text-[11px]">
          <span className="font-mono text-[#9BA7B4]">
            Live execution (disabled)
          </span>
          <span className="font-mono text-[#6E7785]">pnl: null</span>
        </div>
      </div>

      {/* Card 4: Mock Executions / Simulations */}
      <div className="aegis-card rounded-xl p-4 transition hover:border-[#4EE1C2]/35">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="flex h-10 w-10 shrink-0 items-center justify-center rounded-lg border border-[#4EE1C2]/25 bg-[#4EE1C2]/10 text-[#4EE1C2]">
              <Code2 className="h-5 w-5" />
            </div>
            <div>
              <div className="text-xs font-medium text-[#9BA7B4]">
                Mock Executions
              </div>
              <div className="mt-0.5 font-mono text-2xl font-bold tracking-tight text-[#E6EDF3]">
                {animMock}
              </div>
            </div>
          </div>
          <AnimatedSparkline
            points={[1, 1, 2, 1, 2, 3, 2, Math.max(1, mockExecutions + 2)]}
            strokeColor="#4EE1C2"
            fillId="spark-mock"
          />
        </div>
        <div className="mt-3 flex items-center justify-between border-t border-[#2A3542]/60 pt-2.5 text-[11px]">
          <span className="font-mono text-[#9BA7B4]">
            Mode: {sourceMode}
          </span>
          <span className="text-[#6E7785]">
            Unresolved: {metrics?.unresolved_orders ?? 0}
          </span>
        </div>
      </div>
    </section>
  );
}
