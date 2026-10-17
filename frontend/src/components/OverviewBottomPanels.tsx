"use client";

import React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Ban,
  ChevronDown,
  ChevronRight,
  Eye,
  FileText,
  Shield,
} from "lucide-react";
import { extractAtkReceipts } from "@/lib/view-helpers";
import type { Capability, EventItem } from "@/lib/types";

interface OverviewBottomPanelsProps {
  events: EventItem[];
  capabilities: Record<string, Capability>;
  runId?: string | null;
  backendLive?: boolean;
  sourceMode?: string;
  layaAbstained?: boolean;
  executionEnabled?: boolean;
}

export function OverviewBottomPanels({
  events,
  capabilities,
  runId,
  backendLive = false,
  sourceMode = "MARKET_ONLY",
  layaAbstained = true,
  executionEnabled = false,
}: OverviewBottomPanelsProps) {
  const [showAllCapabilities, setShowAllCapabilities] = React.useState(false);

  const recentEvents = React.useMemo(
    () => [...events].slice(-5).reverse(),
    [events]
  );

  const receipts = React.useMemo(
    () => extractAtkReceipts(events, runId ?? undefined),
    [events, runId]
  );

  const totalAtkMs =
    receipts.length > 0
      ? Math.round(
          receipts.reduce(
            (acc, r) =>
              acc + (typeof r.elapsed_ms === "number" ? r.elapsed_ms : 0),
            0
          )
        )
      : null;

  const getEventBadge = (ev: EventItem) => {
    if (ev.type === "RISK_GATE" || ev.type === "RISK_CHECK") {
      const reasons = Array.isArray(ev.details?.reasons)
        ? (ev.details?.reasons as string[])
        : [];
      const isVoluntaryNoTrade = reasons.includes("no_trade_proposed");
      if (isVoluntaryNoTrade) {
        return {
          label: "SAFETY_GATE",
          className: "border-[#F59E0B]/40 bg-[#F59E0B]/12 text-[#F59E0B]",
        };
      }
      return {
        label: "POLICY_VETOED",
        className: "border-[#EF4444]/40 bg-[#EF4444]/12 text-[#EF4444]",
      };
    }
    if (ev.type === "NO_TRADE") {
      return {
        label: "NO_TRADE",
        className: "border-[#F59E0B]/40 bg-[#F59E0B]/12 text-[#F59E0B]",
      };
    }
    if (ev.type === "OBSERVE" || ev.type === "ATK_RECEIPT") {
      return {
        label: "OBSERVED",
        className: "border-[#4EE1C2]/40 bg-[#4EE1C2]/12 text-[#4EE1C2]",
      };
    }
    if (ev.type === "AUDIT") {
      return {
        label: "RECORDED",
        className: "border-[#4EE1C2]/40 bg-[#4EE1C2]/12 text-[#4EE1C2]",
      };
    }
    return {
      label: ev.type,
      className: "border-[#2A3542] bg-[#1A222B] text-[#9BA7B4]",
    };
  };

  const getEventIcon = (type: string) => {
    if (type === "OBSERVE" || type === "ATK_RECEIPT") {
      return <Eye className="h-3.5 w-3.5 text-[#4EE1C2]" />;
    }
    if (type === "RISK_GATE" || type === "RISK_CHECK" || type === "NO_TRADE") {
      return <Ban className="h-3.5 w-3.5 text-[#F59E0B]" />;
    }
    if (type === "AUDIT") {
      return <Shield className="h-3.5 w-3.5 text-[#4EE1C2]" />;
    }
    return <FileText className="h-3.5 w-3.5 text-[#9BA7B4]" />;
  };

  const atkMarketPass =
    capabilities.ATK_MARKET?.status === "PASS" ||
    capabilities.ATK_MARKET_READ?.status === "PASS";
  const mcpPass = capabilities.ATK_MCP_CALL_TOOL?.status === "PASS";
  const layaStatus = capabilities.LAYA?.status ?? "NOT_TESTED";
  const evrenStatus = capabilities.EVREN?.status ?? "NOT_TESTED";
  const erc8004Status = capabilities.ERC8004?.status ?? "NOT_TESTED";
  const demoStatus =
    capabilities.ATK_DEMO_ORDER_SUBMISSION?.status ??
    capabilities.ATK_DEMO?.status ??
    "NOT_TESTED";

  const isMock = sourceMode === "MOCK";
  const policyEvent = [...events].reverse().find(event => event.type === "RISK_GATE" && (!runId || event.run_id === runId));
  const policyMs = policyEvent?.details?.policy_latency_ms;
  const measuredPolicy = typeof policyMs === "number" && Number.isFinite(policyMs) && policyMs >= 0;
  const modelsConnected = backendLive && !isMock && layaStatus === "PASS" && evrenStatus === "PASS";
  const demoReady = backendLive && executionEnabled && sourceMode === "OKX_DEMO";

  const systemRows = [
    {
      label: "Market Data (OKX ATK CLI + MCP)",
      status: isMock
        ? "Mock Simulation"
        : backendLive && atkMarketPass
        ? "Last ATK read verified"
        : atkMarketPass
        ? "Historical ATK Evidence"
        : "Unavailable",
      dot: isMock
        ? "bg-[#F59E0B]"
        : backendLive && atkMarketPass
        ? "bg-[#22C55E]"
        : "bg-[#F59E0B]",
      textClass: isMock
        ? "text-[#F59E0B]"
        : backendLive && atkMarketPass
        ? "text-[#4EE1C2]"
        : "text-[#F59E0B]",
      meta: isMock
        ? "scripted"
        : totalAtkMs
        ? `${totalAtkMs} ms`
        : mcpPass
        ? "site=tr"
        : "offline",
    },
    {
      label: "Risk Engine (Python Policy)",
      status: measuredPolicy ? "Deterministic check recorded" : "Awaiting measured cycle",
      dot: measuredPolicy ? "bg-[#22C55E]" : "bg-[#6E7785]",
      textClass: measuredPolicy ? "text-[#4EE1C2]" : "text-[#9BA7B4]",
      meta: measuredPolicy ? `${policyMs.toFixed(3)} ms` : "NOT_MEASURED",
    },
    {
      label: "AI Models (LAYA / EVREN)",
      status:
        modelsConnected
          ? layaAbstained ? "Connected · LAYA abstaining" : "Connected · Advisory only"
          : isMock
          ? "Scripted (Mock)"
          : "Safe Fallback Active",
      dot:
        modelsConnected && !layaAbstained
          ? "bg-[#22C55E]"
          : "bg-[#F59E0B]",
      textClass:
        modelsConnected && !layaAbstained
          ? "text-[#4EE1C2]"
          : "text-[#F59E0B]",
      meta: `${layaStatus} / ${evrenStatus}`,
    },
    {
      label: "Avalanche Fuji (ERC-8004)",
      status:
        erc8004Status === "PASS"
          ? "Registered & Verified"
          : "Verification unavailable",
      dot: erc8004Status === "PASS" ? "bg-[#22C55E]" : "bg-[#F59E0B]",
      textClass:
        erc8004Status === "PASS" ? "text-[#4EE1C2]" : "text-[#F59E0B]",
      meta: erc8004Status === "PASS" ? "Chain 43113" : "NOT_VERIFIED",
    },
    {
      label: "Exchange (Live / Demo Trade)",
      status: demoReady ? "Demo configured · Policy gated" : "Read-only · Safe",
      dot: "bg-[#6E7785]",
      textClass: "text-[#9BA7B4]",
      meta: `Order proof: ${demoStatus}`,
    },
  ];

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      {/* Left 7 Cols: LATEST ACTIVITY */}
      <section
        aria-label="Latest Activity Preview"
        className="aegis-card lg:col-span-7 flex flex-col justify-between rounded-2xl p-5"
      >
        <div>
          <div className="mb-4 flex items-center justify-between">
            <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9BA7B4]">
              LATEST ACTIVITY
            </span>
            <Link
              href="/activity"
              className="inline-flex items-center gap-1 text-xs font-medium text-[#9BA7B4] hover:text-[#4EE1C2] transition"
            >
              <span>View all ({events.length})</span>
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>

          <div className="divide-y divide-[#2A3542]/50">
            {recentEvents.map((ev, idx) => {
              const badge = getEventBadge(ev);
              const timeStr = ev.timestamp
                ? ev.timestamp.replace("T", " ").slice(11, 19)
                : "—";

              return (
                <Link
                  key={ev.id || `${ev.type}-${idx}`}
                  href={`/activity${ev.id ? `?eventId=${ev.id}` : ""}`}
                  className="group flex flex-wrap items-center justify-between gap-3 py-3 transition hover:bg-[#1A222B]/35 px-2 -mx-2 rounded-lg"
                >
                  <div className="flex items-center gap-3 min-w-0 flex-1">
                    <span className="font-mono text-xs text-[#6E7785] shrink-0">
                      {timeStr}
                    </span>
                    <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-md border border-[#2A3542] bg-[#11161D]">
                      {getEventIcon(ev.type)}
                    </span>
                    <span className="font-mono text-xs font-semibold text-[#E6EDF3] shrink-0">
                      BTC/USDT
                    </span>
                    <span className="truncate text-xs text-[#9BA7B4] group-hover:text-[#E6EDF3] transition">
                      {ev.message}
                    </span>
                  </div>

                  <span
                    className={`shrink-0 rounded-full border px-2.5 py-0.5 font-mono text-[10px] font-semibold ${badge.className}`}
                  >
                    {badge.label}
                  </span>
                </Link>
              );
            })}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-[#2A3542]/60 pt-3 text-[11px] text-[#6E7785]">
          <span>
            Off-chain reasoning & deterministic risk policy · Avalanche Fuji
            43113 registry ready
          </span>
          <Link
            href="/activity"
            className="font-mono text-[#4EE1C2] hover:underline"
          >
            Open Audit Console →
          </Link>
        </div>
      </section>

      {/* Right 5 Cols: SYSTEM STATUS & CAPABILITIES */}
      <section
        aria-label="System Status & Capabilities"
        className="aegis-card lg:col-span-5 flex flex-col justify-between rounded-2xl p-5"
      >
        <div>
          <div className="mb-4 flex items-center justify-between">
            <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9BA7B4]">
              SYSTEM STATUS
            </span>
            <span className="font-mono text-[10px] text-[#6E7785]">
              {backendLive ? "Live /api/capabilities" : "Recorded capabilities"}
            </span>
          </div>

          <div className="divide-y divide-[#2A3542]/50">
            {systemRows.map((row) => (
              <div
                key={row.label}
                className="flex items-center justify-between gap-3 py-2.5 text-xs"
              >
                <span className="text-[#9BA7B4]">{row.label}</span>
                <div className="flex items-center gap-3">
                  <span
                    className={`inline-flex items-center gap-1.5 font-medium ${row.textClass}`}
                  >
                    <span className={`h-2 w-2 rounded-full ${row.dot}`} />
                    {row.status}
                  </span>
                  <span className="w-24 text-right font-mono text-[11px] text-[#6E7785]">
                    {row.meta}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Progressive disclosure for all 12+ raw capability keys */}
        <div className="mt-4 border-t border-[#2A3542]/60 pt-3">
          <button
            type="button"
            onClick={() => setShowAllCapabilities((prev) => !prev)}
            className="flex w-full items-center justify-between text-left font-mono text-[11px] text-[#9BA7B4] hover:text-[#4EE1C2] transition"
          >
            <span>
              Raw Capability Matrix ({Object.keys(capabilities).length} keys)
            </span>
            {showAllCapabilities ? (
              <ChevronDown className="h-3.5 w-3.5" />
            ) : (
              <ChevronRight className="h-3.5 w-3.5" />
            )}
          </button>

          {showAllCapabilities && (
            <div className="mt-2.5 max-h-48 space-y-1.5 overflow-y-auto pr-1 animate-fade-up">
              {Object.entries(capabilities).map(([key, cap]) => (
                <div
                  key={key}
                  className="flex items-center justify-between rounded-lg border border-[#2A3542]/70 bg-[#0A0D10]/70 px-2.5 py-1.5 font-mono text-[10px]"
                >
                  <span className="text-[#E6EDF3]">{key}</span>
                  <span
                    className={`rounded px-1.5 py-0.5 font-semibold ${
                      cap.status === "PASS"
                        ? "bg-[#4EE1C2]/15 text-[#4EE1C2]"
                        : cap.status === "FAIL"
                        ? "bg-[#EF4444]/15 text-[#EF4444]"
                        : "bg-[#1A222B] text-[#9BA7B4]"
                    }`}
                  >
                    {cap.status}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </section>
    </div>
  );
}
