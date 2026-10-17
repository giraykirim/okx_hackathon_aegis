"use client";

import React from "react";
import {
  ChevronDown,
  ChevronRight,
  Clock,
  Cpu,
  FileSearch,
  Lock,
  Shield,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";
import {
  deriveDecisionSemantics,
  deriveRuntimeStatusModel,
  describeEvrenModelState,
  describeLayaModelState,
  explainRiskReason,
  formatAccountBalance,
} from "@/lib/view-helpers";
import type {
  Capability,
  Classification,
  Decision,
  Observation,
} from "@/lib/types";

interface HeroDecisionCardProps {
  decision: Decision | null;
  classification: Classification | null;
  observation: Observation | null;
  capabilities?: Record<string, Capability>;
  backendLive?: boolean;
  activeScenario?: string;
  onInspectEvidenceId?: (id: string) => void;
}

export function HeroDecisionCard({
  decision,
  classification,
  observation,
  capabilities,
  backendLive = false,
  activeScenario = "live_backend",
  onInspectEvidenceId,
}: HeroDecisionCardProps) {
  const [expandedDetails, setExpandedDetails] = React.useState(false);
  const accountInfo = formatAccountBalance(observation);

  if (!decision) {
    return (
      <section className="aegis-card-hero rounded-2xl p-6">
        <div className="flex items-center gap-4">
          <div className="aegis-shield-ring flex h-16 w-16 shrink-0 items-center justify-center rounded-full border border-[#4EE1C2]/30 text-[#4EE1C2]">
            <Shield className="h-7 w-7" />
          </div>
          <div>
            <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[#9BA7B4]">
              LATEST DECISION
            </div>
            <h2 className="mt-1 text-2xl font-bold tracking-tight text-[#E6EDF3]">
              Awaiting Evaluation Cycle
            </h2>
            <p className="mt-1 text-sm text-[#9BA7B4]">
              No persisted decision in current snapshot (`latest_decision=null`).
              System remains in safe read-only monitoring mode.
            </p>
          </div>
        </div>
      </section>
    );
  }

  const semantics = deriveDecisionSemantics(decision);
  const layaState = describeLayaModelState(classification, capabilities);
  const evrenState = describeEvrenModelState(decision, capabilities);
  const runtimeStatus = deriveRuntimeStatusModel({
    backendReachable: backendLive,
    isOfflineFixture: !backendLive,
    activeScenario,
    sourceMode: decision.source_mode,
    lastTimestampIso: observation?.observed_at || decision.timestamp,
  });

  const isMock = decision.source_mode === "MOCK";
  const primaryReason = decision.risk_reasons[0]
    ? explainRiskReason(decision.risk_reasons[0])
    : null;

  const verdictChip =
    semantics.verdictType === "POLICY_VETOED"
      ? {
          text: "POLICY_VETOED",
          className: "border-[#EF4444]/40 bg-[#EF4444]/12 text-[#EF4444]",
        }
      : semantics.verdictType === "NO_TRADE"
      ? {
          text: "NO_TRADE",
          className: "border-[#F59E0B]/40 bg-[#F59E0B]/12 text-[#F59E0B]",
        }
      : {
          text: isMock ? "MOCK_APPROVED" : "POLICY_APPROVED",
          className: "border-[#4EE1C2]/40 bg-[#4EE1C2]/12 text-[#4EE1C2]",
        };

  return (
    <section
      aria-label="Latest Decision Hero"
      className="aegis-card-hero rounded-2xl p-6 transition-all duration-300"
    >
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-12 lg:items-center">
        {/* Left 7 Cols: Shield Emblem + Headline */}
        <div className="flex flex-col gap-5 sm:flex-row sm:items-center lg:col-span-7">
          <div className="relative flex h-20 w-20 shrink-0 items-center justify-center">
            <div
              className={`aegis-shield-ring absolute inset-0 rounded-full border ${
                semantics.verdictType === "POLICY_VETOED"
                  ? "border-[#EF4444]/35"
                  : "border-[#4EE1C2]/30"
              }`}
            />
            <div
              className={`relative flex h-14 w-14 items-center justify-center rounded-full border bg-[#0A0D10]/90 ${
                semantics.verdictType === "POLICY_VETOED"
                  ? "border-[#EF4444]/45 text-[#EF4444]"
                  : "border-[#4EE1C2]/40 text-[#4EE1C2]"
              }`}
            >
              {semantics.verdictType === "POLICY_VETOED" ? (
                <ShieldAlert className="h-7 w-7 text-[#EF4444]" />
              ) : semantics.verdictType === "NO_TRADE" ? (
                <Shield className="h-7 w-7 text-[#4EE1C2]" />
              ) : (
                <ShieldCheck className="h-7 w-7 text-[#4EE1C2]" />
              )}
            </div>
          </div>

          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9BA7B4]">
                LATEST DECISION
              </span>
              <span
                className={`rounded-full border px-2 py-0.5 font-mono text-[10px] font-semibold ${
                  runtimeStatus.tone === "mint"
                    ? "border-[#4EE1C2]/35 bg-[#4EE1C2]/10 text-[#4EE1C2]"
                    : "border-[#F59E0B]/40 bg-[#F59E0B]/12 text-[#F59E0B]"
                }`}
              >
                {runtimeStatus.badgeLabel}
              </span>
              <span className="rounded-full border border-[#2A3542] bg-[#11161D] px-2 py-0.5 font-mono text-[10px] text-[#9BA7B4]">
                {decision.source_mode} · {decision.execution_status}
              </span>
            </div>

            <h2 className="text-2xl font-bold tracking-tight text-[#E6EDF3] sm:text-3xl">
              {semantics.headline}
            </h2>

            <p className="max-w-xl text-sm leading-relaxed text-[#9BA7B4]">
              {semantics.subheadline}
            </p>
          </div>
        </div>

        {/* Right 5 Cols: Structured Metadata Table */}
        <div className="border-t border-[#2A3542]/70 pt-4 lg:col-span-5 lg:border-l lg:border-t-0 lg:pl-6 lg:pt-0">
          <dl className="space-y-2.5 text-xs">
            <div className="flex items-center justify-between gap-4">
              <dt className="text-[#6E7785]">Asset</dt>
              <dd className="font-mono font-semibold text-[#E6EDF3]">
                {decision.symbol}{" "}
                {observation?.price ? (
                  <span className="text-[#9BA7B4]">
                    (@ {observation.price} USDT)
                  </span>
                ) : null}
              </dd>
            </div>

            <div className="flex items-center justify-between gap-4">
              <dt className="text-[#6E7785]">Evaluated Proposal</dt>
              <dd className="font-medium text-[#E6EDF3]">
                {decision.proposed_action === "NO_TRADE"
                  ? "NO_TRADE (No order requested)"
                  : `${decision.proposed_action} ${decision.quantity} BTC`}{" "}
                ·{" "}
                <span
                  className={`font-mono ${
                    !layaState.isAvailable && !layaState.isScriptedMock
                      ? "text-[#F59E0B]"
                      : decision.laya_label === "CONTINUE"
                      ? "text-[#4EE1C2]"
                      : decision.laya_label === "REVIEW"
                      ? "text-[#F59E0B]"
                      : "text-[#EF4444]"
                  }`}
                >
                  {layaState.isAvailable || layaState.isScriptedMock
                    ? `LAYA: ${decision.laya_label}`
                    : `LAYA Unavailable (${layaState.actionLabel})`}
                </span>
              </dd>
            </div>

            <div className="flex items-center justify-between gap-4">
              <dt className="text-[#6E7785]">Risk Verdict</dt>
              <dd>
                <span
                  className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 font-mono text-[11px] font-semibold ${verdictChip.className}`}
                >
                  <span className="h-1.5 w-1.5 rounded-full bg-current" />
                  {verdictChip.text}
                </span>
              </dd>
            </div>

            <div className="flex items-start justify-between gap-4">
              <dt className="text-[#6E7785] shrink-0">Primary Rule</dt>
              <dd className="text-right font-medium text-[#E6EDF3]">
                {primaryReason
                  ? `${primaryReason.title} (${decision.risk_reasons.length} rules)`
                  : "All deterministic rules satisfied"}
              </dd>
            </div>

            <div className="flex items-center justify-between gap-4">
              <dt className="text-[#6E7785]">Recorded At</dt>
              <dd className="inline-flex items-center gap-1.5 font-mono text-[#9BA7B4]">
                <Clock className="h-3 w-3 text-[#6E7785]" />
                <span>
                  {decision.timestamp
                    ? decision.timestamp.replace("T", " ").slice(0, 19) + " UTC"
                    : "N/A"}{" "}
                  ({runtimeStatus.relativeAgeText})
                </span>
              </dd>
            </div>
          </dl>
        </div>
      </div>

      {/* Progressive Disclosure Bar (Section 13: Clean Summary + Expandable Rules) */}
      <div className="mt-5 flex flex-wrap items-center justify-between gap-3 border-t border-[#2A3542]/60 pt-3.5">
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs font-medium text-[#9BA7B4]">
            {semantics.isTradeBlockedByPolicy
              ? `${decision.risk_reasons.length} safety checks prevented execution:`
              : `${decision.risk_reasons.length} safety checks enforced read-only posture:`}
          </span>
          {decision.risk_reasons.slice(0, 3).map((rule) => (
            <span
              key={rule}
              className="rounded-md border border-[#2A3542] bg-[#11161D] px-2 py-0.5 font-mono text-[11px] text-[#E6EDF3]"
            >
              {rule}
            </span>
          ))}
          {decision.risk_reasons.length > 3 && !expandedDetails && (
            <span className="rounded-md border border-[#2A3542]/70 bg-[#0A0D10] px-2 py-0.5 font-mono text-[11px] text-[#9BA7B4]">
              +{decision.risk_reasons.length - 3} more
            </span>
          )}
        </div>

        <button
          type="button"
          onClick={() => setExpandedDetails((prev) => !prev)}
          className="inline-flex items-center gap-1.5 rounded-lg border border-[#2A3542] bg-[#11161D]/90 px-3 py-1.5 text-xs font-medium text-[#9BA7B4] hover:border-[#4EE1C2]/40 hover:text-[#E6EDF3] transition"
        >
          {expandedDetails ? (
            <ChevronDown className="h-3.5 w-3.5 text-[#4EE1C2]" />
          ) : (
            <ChevronRight className="h-3.5 w-3.5 text-[#4EE1C2]" />
          )}
          <span>
            {expandedDetails
              ? "Hide Risk Rules & Model Provenance"
              : `${decision.risk_reasons.length} safety checks prevented execution — View Risk Rules`}
          </span>
        </button>
      </div>

      {/* Expandable Progressive Disclosure Drawer */}
      {expandedDetails && (
        <div className="mt-4 space-y-4 border-t border-[#2A3542]/60 pt-4 animate-fade-up">
          {/* Rule Explanations */}
          {decision.risk_reasons.length > 0 && (
            <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2 lg:grid-cols-3">
              {decision.risk_reasons.map((reason) => {
                const info = explainRiskReason(reason);
                return (
                  <div
                    key={reason}
                    className="rounded-xl border border-[#2A3542] bg-[#0A0D10]/80 p-3"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span
                        className={`rounded px-2 py-0.5 font-mono text-[10px] font-semibold border ${
                          semantics.isTradeBlockedByPolicy
                            ? "bg-[#EF4444]/15 text-[#EF4444] border-[#EF4444]/30"
                            : "bg-[#F59E0B]/15 text-[#F59E0B] border-[#F59E0B]/30"
                        }`}
                      >
                        {info.ruleId}
                      </span>
                      <span className="font-mono text-[10px] text-[#6E7785]">
                        {semantics.isTradeBlockedByPolicy
                          ? "POLICY VETO"
                          : "SAFETY GATE"}
                      </span>
                    </div>
                    <div className="mt-1.5 text-xs font-semibold text-[#E6EDF3]">
                      {info.title}
                    </div>
                    <p className="mt-0.5 text-[11px] leading-relaxed text-[#9BA7B4]">
                      {info.explanation}
                    </p>
                  </div>
                );
              })}
            </div>
          )}

          {/* 3-Column Sub-Model & Account Breakdown (Sections 6 & 7: Honest LAYA/EVREN Fallback) */}
          <div className="grid grid-cols-1 gap-3 lg:grid-cols-3">
            {/* LAYA (Section 6) */}
            <div className="rounded-xl border border-[#2A3542] bg-[#0A0D10]/70 p-3.5">
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#E6EDF3]">
                  <Cpu className="h-3.5 w-3.5 text-[#4EE1C2]" />
                  {layaState.statusTitle}
                </span>
                <span className="rounded border border-[#F59E0B]/35 bg-[#F59E0B]/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-[#F59E0B]">
                  {layaState.actionLabel}
                </span>
              </div>
              <p className="mt-1.5 text-[11px] text-[#9BA7B4]">
                {layaState.subtitle}
              </p>
              <div className="mt-2.5 space-y-1 border-t border-[#2A3542]/50 pt-2 font-mono text-[11px] text-[#9BA7B4]">
                <div className="flex justify-between">
                  <span>Confidence:</span>
                  <span className="text-[#E6EDF3]">
                    {layaState.confidenceText.replace("Confidence: ", "")}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Model Latency:</span>
                  <span className="text-[#E6EDF3]">
                    {layaState.latencyText.replace("Model latency: ", "")}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Model Source:</span>
                  <span className="text-[#E6EDF3]">
                    {classification?.model_version ?? "advisory-fallback"}
                  </span>
                </div>
              </div>
            </div>

            {/* EVREN (Section 7) */}
            <div className="rounded-xl border border-[#2A3542] bg-[#0A0D10]/70 p-3.5">
              <div className="flex items-center justify-between gap-2">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#E6EDF3]">
                  <Lock className="h-3.5 w-3.5 text-[#3B82F6]" />
                  {evrenState.statusTitle}
                </span>
                <span className="rounded border border-[#F59E0B]/35 bg-[#F59E0B]/10 px-2 py-0.5 font-mono text-[10px] font-semibold text-[#F59E0B]">
                  {evrenState.badgeText}
                </span>
              </div>
              <p className="mt-1.5 rounded border border-[#2A3542]/70 bg-[#11161D] p-2 font-mono text-[11px] text-[#9BA7B4]">
                {evrenState.subtitle}
              </p>
              <div className="mt-2 space-y-1 font-mono text-[11px] text-[#9BA7B4]">
                <div className="flex justify-between">
                  <span>Proposed Action:</span>
                  <span className="text-[#E6EDF3]">
                    {decision.proposed_action} ({decision.quantity} BTC)
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Model Latency:</span>
                  <span className="text-[#E6EDF3]">
                    {evrenState.latencyText.replace("Model latency: ", "")}
                  </span>
                </div>
                <div className="flex justify-between text-[10px] text-[#6E7785]">
                  <span>Tool Invocation: DISABLED</span>
                  <span>Intent: {decision.intent_id.slice(0, 10)}…</span>
                </div>
              </div>
            </div>

            {/* Market & Account Provenance */}
            <div className="rounded-xl border border-[#2A3542] bg-[#0A0D10]/70 p-3.5">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 text-xs font-semibold text-[#E6EDF3]">
                  <ShieldAlert className="h-3.5 w-3.5 text-[#F59E0B]" />
                  Account & Market Provenance
                </span>
                <span className="font-mono text-[10px] font-bold text-[#F59E0B]">
                  ACCOUNT: {accountInfo.statusLabel}
                </span>
              </div>
              <div className="mt-2 space-y-1 font-mono text-[11px] text-[#9BA7B4]">
                <div className="flex justify-between">
                  <span>Bid / Ask:</span>
                  <span className="text-[#E6EDF3]">
                    {observation
                      ? `${observation.bid} / ${observation.ask}`
                      : "N/A"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Quote Balance:</span>
                  <span className="text-[#F59E0B]">
                    {accountInfo.quoteDisplay}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Venue Order ID:</span>
                  <span className="text-[#E6EDF3]">
                    {decision.venue_order_id ?? "null (NOT_SENT)"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span>Runtime State:</span>
                  <span className="text-[#E6EDF3]">
                    {runtimeStatus.badgeLabel}
                  </span>
                </div>
              </div>
            </div>
          </div>

          {/* Evidence IDs */}
          {decision.evidence_ids.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 pt-1">
              <span className="inline-flex items-center gap-1 text-[11px] font-medium text-[#9BA7B4]">
                <FileSearch className="h-3.5 w-3.5 text-[#4EE1C2]" />
                Linked Evidence Receipts:
              </span>
              {decision.evidence_ids.map((evId) => (
                <button
                  key={evId}
                  type="button"
                  onClick={() => onInspectEvidenceId?.(evId)}
                  className="rounded border border-[#2A3542] bg-[#11161D] px-2 py-0.5 font-mono text-[10px] text-[#4EE1C2] hover:border-[#4EE1C2]/50 transition"
                >
                  {evId.slice(0, 12)}…
                </button>
              ))}
            </div>
          )}
        </div>
      )}
    </section>
  );
}
