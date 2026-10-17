"use client";

import React from "react";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  Clock,
  ExternalLink,
  FlaskConical,
  Gavel,
  Loader2,
  Scale,
  Shield,
  ShieldAlert,
  Slash,
  Sparkles,
} from "lucide-react";
import type {
  CouncilLifecycleState,
  CouncilMemberStance,
  CouncilMemberVerdict,
  CouncilSeatStatus,
  EventItem,
  Snapshot,
} from "@/lib/types";
import { deriveTradeCourtSession, explainRiskReason } from "@/lib/view-helpers";

interface TradeCourtCouncilProps {
  snapshot: Snapshot | null;
  events: EventItem[];
  onInspectEvidenceId?: (id: string) => void;
}

const PREVIEW_STATES: Array<{
  key: CouncilLifecycleState | "LIVE_RUNTIME";
  label: string;
}> = [
  { key: "LIVE_RUNTIME", label: "Runtime / Event Stream" },
  { key: "COMPLETED", label: "Mock: Completed" },
  { key: "DEGRADED", label: "Mock: Degraded" },
  { key: "SKIPPED", label: "Mock: Skipped" },
  { key: "UNAVAILABLE", label: "Mock: Unavailable" },
  { key: "LOADING", label: "Mock: Loading" },
];

function getLifecycleBadgeStyle(state: CouncilLifecycleState): {
  label: string;
  badgeClass: string;
  icon: React.ReactNode;
} {
  switch (state) {
    case "COMPLETED":
      return {
        label: "COUNCIL COMPLETED",
        badgeClass: "border-[#4EE1C2]/40 bg-[#4EE1C2]/10 text-[#4EE1C2]",
        icon: <CheckCircle2 className="h-3.5 w-3.5" />,
      };
    case "DEGRADED":
      return {
        label: "COUNCIL DEGRADED (FAIL-CLOSED)",
        badgeClass: "border-[#F59E0B]/40 bg-[#F59E0B]/10 text-[#F59E0B]",
        icon: <AlertTriangle className="h-3.5 w-3.5" />,
      };
    case "SKIPPED":
      return {
        label: "COUNCIL SKIPPED (SHORT-CIRCUIT)",
        badgeClass: "border-[#F59E0B]/40 bg-[#F59E0B]/10 text-[#F59E0B]",
        icon: <Slash className="h-3.5 w-3.5" />,
      };
    case "UNAVAILABLE":
      return {
        label: "AI SEATS UNAVAILABLE (POLICY FALLBACK)",
        badgeClass: "border-[#2A3542] bg-[#161D26] text-[#9BA7B4]",
        icon: <Shield className="h-3.5 w-3.5 text-[#4EE1C2]" />,
      };
    case "LOADING":
      return {
        label: "DELIBERATION IN FLIGHT",
        badgeClass: "border-[#3B82F6]/40 bg-[#3B82F6]/10 text-[#3B82F6]",
        icon: <Loader2 className="h-3.5 w-3.5 animate-spin" />,
      };
  }
}

function getSeatStatusStyle(status: CouncilSeatStatus): {
  label: string;
  className: string;
} {
  switch (status) {
    case "COMPLETED":
      return {
        label: "COMPLETED",
        className: "border-[#4EE1C2]/35 bg-[#4EE1C2]/10 text-[#4EE1C2]",
      };
    case "MOCK_SCRIPTED":
      return {
        label: "MOCK SCRIPTED",
        className: "border-[#F59E0B]/40 bg-[#F59E0B]/12 text-[#F59E0B]",
      };
    case "DEGRADED":
      return {
        label: "DEGRADED",
        className: "border-[#F59E0B]/40 bg-[#F59E0B]/12 text-[#F59E0B]",
      };
    case "SKIPPED":
      return {
        label: "SKIPPED",
        className: "border-[#2A3542] bg-[#161D26] text-[#9BA7B4]",
      };
    case "UNAVAILABLE":
      return {
        label: "UNAVAILABLE",
        className: "border-[#2A3542] bg-[#161D26] text-[#9BA7B4]",
      };
    case "LOADING":
      return {
        label: "LOADING...",
        className: "border-[#3B82F6]/40 bg-[#3B82F6]/12 text-[#3B82F6]",
      };
  }
}

function getStanceBadgeStyle(stance: CouncilMemberStance): {
  label: string;
  className: string;
} {
  switch (stance) {
    case "APPROVE":
      return {
        label: "STANCE: PROCEED",
        className: "border-[#4EE1C2]/35 bg-[#4EE1C2]/10 text-[#4EE1C2]",
      };
    case "CAUTION":
      return {
        label: "STANCE: REVIEW / CAUTION",
        className: "border-[#F59E0B]/35 bg-[#F59E0B]/10 text-[#F59E0B]",
      };
    case "VETO":
      return {
        label: "STANCE: VETO / HALT",
        className: "border-[#EF4444]/40 bg-[#EF4444]/12 text-[#EF4444]",
      };
    case "ABSTAIN":
      return {
        label: "STANCE: ABSTAIN (NO_TRADE)",
        className: "border-[#2A3542] bg-[#0A0D10] text-[#9BA7B4]",
      };
  }
}

export function TradeCourtCouncil({
  snapshot,
  events,
  onInspectEvidenceId,
}: TradeCourtCouncilProps) {
  const [previewMode, setPreviewMode] = React.useState<
    CouncilLifecycleState | "LIVE_RUNTIME"
  >("LIVE_RUNTIME");
  const [selectedSeatId, setSelectedSeatId] = React.useState<string | null>(
    null
  );

  const session = React.useMemo(
    () =>
      deriveTradeCourtSession({
        snapshot,
        events,
        mockPreviewState:
          previewMode === "LIVE_RUNTIME" ? null : previewMode,
      }),
    [snapshot, events, previewMode]
  );

  const lifecycleStyle = getLifecycleBadgeStyle(session.state);

  const activeSeat: CouncilMemberVerdict | null = React.useMemo(() => {
    if (!selectedSeatId) return null;
    return session.seats.find((s) => s.seatId === selectedSeatId) ?? null;
  }, [session.seats, selectedSeatId]);

  return (
    <section
      aria-label="TradeCourt Council Deliberation"
      className="aegis-card rounded-2xl p-5 transition-all duration-200"
    >
      {/* Top Header + State Inspector Switcher */}
      <div className="flex flex-col justify-between gap-4 border-b border-[#2A3542]/70 pb-4 lg:flex-row lg:items-center">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <Scale className="h-4 w-4 text-[#4EE1C2]" />
            <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9BA7B4]">
              TRADECOURT DELIBERATION COUNCIL
            </span>
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-semibold ${lifecycleStyle.badgeClass}`}
            >
              {lifecycleStyle.icon}
              {lifecycleStyle.label}
            </span>
            {session.isMockFixture && (
              <span className="inline-flex items-center gap-1.5 rounded-full border border-[#F59E0B]/50 bg-[#F59E0B]/15 px-2.5 py-0.5 font-mono text-[11px] font-semibold text-[#F59E0B]">
                <FlaskConical className="h-3 w-3" />
                MOCK COUNCIL FIXTURE — Not Real EVREN Inference
              </span>
            )}
          </div>
          <h2 className="mt-1.5 text-base font-semibold text-[#E6EDF3] sm:text-lg">
            {session.headline}
          </h2>
          <p className="mt-0.5 text-xs leading-relaxed text-[#9BA7B4]">
            {session.summary}
          </p>
        </div>

        {/* Segmented State Preview Switcher for Visual Testing of all 5 States */}
        <div className="flex flex-col items-start gap-1.5 lg:items-end">
          <span className="font-mono text-[10px] uppercase tracking-wider text-[#6E7785]">
            Council State Inspector (Visual Test Mode)
          </span>
          <div
            role="group"
            aria-label="Council State Inspector"
            className="flex flex-wrap items-center gap-1 rounded-xl border border-[#2A3542] bg-[#0A0D10]/90 p-1"
          >
            {PREVIEW_STATES.map((item) => {
              const active = previewMode === item.key;
              const isMockBtn = item.key !== "LIVE_RUNTIME";
              return (
                <button
                  key={item.key}
                  type="button"
                  onClick={() => setPreviewMode(item.key)}
                  className={`rounded-lg px-2.5 py-1 font-mono text-[11px] font-medium transition ${
                    active
                      ? isMockBtn
                        ? "border border-[#F59E0B]/40 bg-[#F59E0B]/15 text-[#F59E0B]"
                        : "border border-[#4EE1C2]/40 bg-[#4EE1C2]/15 text-[#4EE1C2]"
                      : "text-[#9BA7B4] hover:bg-[#161D26] hover:text-[#E6EDF3]"
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </div>
        </div>
      </div>

      {/* Explicit Truthfulness Banner when viewing Mock Fixture / Scripted Mode */}
      {session.isMockFixture && (
        <div
          role="status"
          className="mt-4 flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#F59E0B]/40 bg-[#F59E0B]/10 px-3.5 py-2.5 text-xs text-[#F59E0B]"
        >
          <div className="flex items-center gap-2">
            <FlaskConical className="h-4 w-4 shrink-0" />
            <span className="font-medium">
              {session.authorityNotice}
            </span>
          </div>
          {previewMode !== "LIVE_RUNTIME" && (
            <button
              type="button"
              onClick={() => setPreviewMode("LIVE_RUNTIME")}
              className="rounded-lg border border-[#F59E0B]/40 bg-[#0A0D10]/60 px-2.5 py-1 font-mono text-[11px] font-semibold text-[#F59E0B] hover:bg-[#0A0D10] transition"
            >
              Return to Runtime Stream
            </button>
          )}
        </div>
      )}

      {/* 4 Council Seat Cards */}
      <div className="mt-4 grid grid-cols-1 gap-3.5 md:grid-cols-2 xl:grid-cols-4">
        {session.seats.map((seat) => {
          const statusBadge = getSeatStatusStyle(seat.status);
          const stanceBadge = getStanceBadgeStyle(seat.stance);
          const isArbiter = !seat.isAdvisoryOnly;
          const isSelected = selectedSeatId === seat.seatId;

          const confidenceDisplay =
            seat.confidence !== null
              ? `${(seat.confidence * 100).toFixed(0)}%`
              : "Not measured";
          const latencyDisplay =
            seat.latencyMs !== null ? `${seat.latencyMs} ms` : "Not measured";

          return (
            <div
              key={seat.seatId}
              onClick={() =>
                setSelectedSeatId((prev) =>
                  prev === seat.seatId ? null : seat.seatId
                )
              }
              role="button"
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  setSelectedSeatId((prev) =>
                    prev === seat.seatId ? null : seat.seatId
                  );
                }
              }}
              className={`group flex flex-col justify-between rounded-xl border p-4 text-left transition-all duration-150 cursor-pointer ${
                isSelected
                  ? "border-[#4EE1C2]/60 bg-[#161D26]"
                  : isArbiter
                  ? "border-[#4EE1C2]/30 bg-[#0A0D10]/90 hover:border-[#4EE1C2]/50"
                  : "border-[#2A3542]/80 bg-[#0A0D10]/70 hover:border-[#2A3542] hover:bg-[#11161D]"
              }`}
            >
              <div>
                {/* Seat Header + Authority Pill */}
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <span
                      className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-lg border ${
                        isArbiter
                          ? "border-[#4EE1C2]/40 bg-[#4EE1C2]/10 text-[#4EE1C2]"
                          : seat.actor === "laya"
                          ? "border-[#F59E0B]/35 bg-[#F59E0B]/10 text-[#F59E0B]"
                          : "border-[#3B82F6]/35 bg-[#3B82F6]/10 text-[#3B82F6]"
                      }`}
                    >
                      {isArbiter ? (
                        <Gavel className="h-3.5 w-3.5" />
                      ) : seat.actor === "laya" ? (
                        <Sparkles className="h-3.5 w-3.5" />
                      ) : (
                        <Bot className="h-3.5 w-3.5" />
                      )}
                    </span>
                    <div>
                      <div className="text-xs font-semibold text-[#E6EDF3]">
                        {seat.roleTitle}
                      </div>
                      <div className="text-[11px] text-[#6E7785]">
                        {seat.subtitle}
                      </div>
                    </div>
                  </div>

                  <span
                    className={`shrink-0 rounded-md border px-1.5 py-0.5 font-mono text-[9px] font-semibold uppercase ${
                      isArbiter
                        ? "border-[#4EE1C2]/40 bg-[#4EE1C2]/15 text-[#4EE1C2]"
                        : "border-[#2A3542] bg-[#11161D] text-[#9BA7B4]"
                    }`}
                  >
                    {isArbiter ? "BINDING GATE" : "ADVISORY SEAT"}
                  </span>
                </div>

                {/* Status + Stance Row */}
                <div className="mt-3 flex flex-wrap items-center gap-1.5">
                  <span
                    className={`rounded-md border px-2 py-0.5 font-mono text-[10px] font-semibold ${statusBadge.className}`}
                  >
                    {statusBadge.label}
                  </span>
                  <span
                    className={`rounded-md border px-2 py-0.5 font-mono text-[10px] font-semibold ${stanceBadge.className}`}
                  >
                    {stanceBadge.label}
                  </span>
                </div>

                {/* Model / Engine Provenance */}
                <div className="mt-2.5 rounded-lg border border-[#2A3542]/60 bg-[#11161D]/90 px-2.5 py-1.5 font-mono text-[11px]">
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-[#6E7785]">Engine:</span>
                    <span className="truncate text-[#E6EDF3]">
                      {seat.modelName ?? "Unavailable (Fallback)"}
                    </span>
                  </div>
                  <div className="mt-1 flex items-center justify-between gap-2 text-[10px]">
                    <span className="text-[#6E7785]">
                      {isArbiter ? "Authority:" : "Confidence:"}
                    </span>
                    <span className="text-[#9BA7B4]">
                      {isArbiter ? "100% Deterministic" : confidenceDisplay}
                    </span>
                  </div>
                  <div className="mt-0.5 flex items-center justify-between gap-2 text-[10px]">
                    <span className="text-[#6E7785]">Latency:</span>
                    <span className="text-[#9BA7B4]">{latencyDisplay}</span>
                  </div>
                </div>

                {/* Seat Rationale */}
                <p className="mt-2.5 text-xs leading-relaxed text-[#9BA7B4]">
                  {seat.rationale}
                </p>
              </div>

              {/* Footer: Flagged Rules + Evidence Link */}
              <div className="mt-3 border-t border-[#2A3542]/50 pt-2.5">
                {seat.flaggedRules.length > 0 ? (
                  <div className="flex flex-wrap gap-1">
                    {seat.flaggedRules.slice(0, 3).map((rule) => (
                      <span
                        key={rule}
                        className="rounded border border-[#EF4444]/30 bg-[#EF4444]/10 px-1.5 py-0.5 font-mono text-[10px] text-[#EF4444]"
                      >
                        {rule}
                      </span>
                    ))}
                    {seat.flaggedRules.length > 3 && (
                      <span className="rounded border border-[#2A3542] bg-[#11161D] px-1.5 py-0.5 font-mono text-[10px] text-[#9BA7B4]">
                        +{seat.flaggedRules.length - 3} more
                      </span>
                    )}
                  </div>
                ) : (
                  <div className="font-mono text-[10px] text-[#6E7785]">
                    No policy rules flagged by this seat
                  </div>
                )}

                <div className="mt-2 flex items-center justify-between font-mono text-[10px] text-[#6E7785]">
                  <span>
                    Evidence:{" "}
                    {seat.evidenceId
                      ? `${seat.evidenceId.slice(0, 10)}…`
                      : "None"}
                  </span>
                  {seat.evidenceId && onInspectEvidenceId && (
                    <button
                      type="button"
                      onClick={(e) => {
                        e.stopPropagation();
                        onInspectEvidenceId(seat.evidenceId!);
                      }}
                      className="inline-flex items-center gap-1 text-[#4EE1C2] hover:underline"
                    >
                      <span>Trace</span>
                      <ExternalLink className="h-2.5 w-2.5" />
                    </button>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>

      {/* Expandable Seat Inspection Drawer when a Seat is Clicked */}
      {activeSeat && (
        <div className="mt-3.5 rounded-xl border border-[#4EE1C2]/30 bg-[#0A0D10]/95 p-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2">
              <span className="font-mono text-xs font-semibold text-[#4EE1C2]">
                SEAT DETAIL: {activeSeat.roleTitle.toUpperCase()}
              </span>
              {activeSeat.isMockData && (
                <span className="rounded border border-[#F59E0B]/40 bg-[#F59E0B]/10 px-2 py-0.5 font-mono text-[10px] text-[#F59E0B]">
                  MOCK DATA — Not Real EVREN Inference
                </span>
              )}
            </div>
            <button
              type="button"
              onClick={() => setSelectedSeatId(null)}
              className="font-mono text-xs text-[#9BA7B4] hover:text-[#E6EDF3]"
            >
              Close [×]
            </button>
          </div>
          <p className="mt-1.5 text-xs text-[#E6EDF3]">{activeSeat.rationale}</p>
          {activeSeat.flaggedRules.length > 0 && (
            <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
              {activeSeat.flaggedRules.map((r) => {
                const info = explainRiskReason(r);
                return (
                  <div
                    key={r}
                    className="rounded-lg border border-[#2A3542] bg-[#11161D] p-2.5"
                  >
                    <div className="font-mono text-[11px] font-semibold text-[#EF4444]">
                      {info.ruleId} — {info.title}
                    </div>
                    <div className="mt-0.5 text-[11px] text-[#9BA7B4]">
                      {info.explanation}
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      )}

      {/* Constitutional Execution Authority Footer */}
      <div className="mt-4 flex flex-col justify-between gap-2 rounded-xl border border-[#2A3542]/70 bg-[#0A0D10]/60 px-3.5 py-2.5 text-xs text-[#9BA7B4] sm:flex-row sm:items-center">
        <div className="flex items-center gap-2">
          <ShieldAlert className="h-4 w-4 shrink-0 text-[#4EE1C2]" />
          <span>
            <strong className="text-[#E6EDF3]">Hard Policy Boundary:</strong>{" "}
            LAYA &amp; EVREN Council seats are strictly advisory. Deterministic
            Python Risk Gate holds 100% veto &amp; execution authority (
            <code className="font-mono text-[#4EE1C2]">
              order_permission=false
            </code>
            ).
          </span>
        </div>
        <div className="flex items-center gap-3 font-mono text-[11px] text-[#6E7785]">
          <span className="inline-flex items-center gap-1">
            <Clock className="h-3 w-3" />
            Deliberation:{" "}
            {session.totalDeliberationMs !== null
              ? `${session.totalDeliberationMs} ms`
              : "Not measured"}
          </span>
          <span>Run: {session.runId.slice(0, 8)}…</span>
        </div>
      </div>
    </section>
  );
}
