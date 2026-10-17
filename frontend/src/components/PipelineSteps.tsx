"use client";

import React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Ban,
  Brain,
  CheckCircle2,
  Eye,
  FileSpreadsheet,
  FileText,
  Shield,
  X,
} from "lucide-react";
import type { PipelineStepView } from "@/lib/view-helpers";

interface PipelineStepsProps {
  steps: PipelineStepView[];
  selectedStepKey?: PipelineStepView["key"] | null;
  onSelectStep?: (step: PipelineStepView) => void;
}

const SHORT_NAMES: Record<PipelineStepView["key"], string> = {
  OBSERVE: "Observe",
  CLASSIFY: "Classify",
  REASON: "Reason",
  RISK_GATE: "Risk Gate",
  ACTION: "Action / No Trade",
  VERIFY: "Verify",
  AUDIT: "Audit",
};

const SHORT_DESCRIPTIONS: Record<PipelineStepView["key"], string> = {
  OBSERVE: "Ingest OKX ATK market data.",
  CLASSIFY: "Identify operational risk class.",
  REASON: "Evaluate bounded proposal.",
  RISK_GATE: "Apply deterministic safety rules.",
  ACTION: "Execution blocked or skipped.",
  VERIFY: "Confirm venue state (if sent).",
  AUDIT: "Record decision & SHA-256 digest.",
};

export function PipelineSteps({
  steps,
  selectedStepKey,
  onSelectStep,
}: PipelineStepsProps) {
  const [activeDetailStep, setActiveDetailStep] =
    React.useState<PipelineStepView | null>(null);

  const getStepIcon = (
    key: PipelineStepView["key"],
    status: PipelineStepView["status"]
  ) => {
    const colorClass =
      status === "COMPLETED" || status === "RUNNING"
        ? "text-[#4EE1C2]"
        : status === "BLOCKED" || status === "VETOED"
        ? "text-[#EF4444]"
        : status === "FALLBACK" || status === "UNAVAILABLE"
        ? "text-[#F59E0B]"
        : "text-[#6E7785]";

    switch (key) {
      case "OBSERVE":
        return <Eye className={`h-4 w-4 ${colorClass}`} />;
      case "CLASSIFY":
        return <FileText className={`h-4 w-4 ${colorClass}`} />;
      case "REASON":
        return <Brain className={`h-4 w-4 ${colorClass}`} />;
      case "RISK_GATE":
        return <Shield className={`h-4 w-4 ${colorClass}`} />;
      case "ACTION":
        return <Ban className={`h-4 w-4 ${colorClass}`} />;
      case "VERIFY":
        return <CheckCircle2 className={`h-4 w-4 ${colorClass}`} />;
      case "AUDIT":
        return <FileSpreadsheet className={`h-4 w-4 ${colorClass}`} />;
    }
  };

  const getBottomStatusLabel = (step: PipelineStepView) => {
    if (step.key === "AUDIT" && step.status === "COMPLETED") {
      return {
        text: "RECORDED",
        dot: "bg-[#4EE1C2]",
        textClass: "text-[#4EE1C2]",
      };
    }

    switch (step.status) {
      case "COMPLETED":
        return {
          text: "COMPLETED",
          dot: "bg-[#4EE1C2]",
          textClass: "text-[#4EE1C2]",
        };
      case "RUNNING":
        return {
          text: "RUNNING",
          dot: "bg-[#4EE1C2] animate-pulse",
          textClass: "text-[#4EE1C2]",
        };
      case "SKIPPED":
        return {
          text: step.key === "ACTION" ? "NO TRADE" : "SKIPPED",
          dot: "bg-[#6E7785]",
          textClass: "text-[#9BA7B4]",
        };
      case "BLOCKED":
      case "VETOED":
        return {
          text:
            step.statusBadgeLabel === "NO_TRADE ENFORCED"
              ? "SAFE GATE"
              : "BLOCKED",
          dot:
            step.statusBadgeLabel === "NO_TRADE ENFORCED"
              ? "bg-[#F59E0B]"
              : "bg-[#EF4444]",
          textClass:
            step.statusBadgeLabel === "NO_TRADE ENFORCED"
              ? "text-[#F59E0B]"
              : "text-[#EF4444]",
        };
      case "FALLBACK":
        return {
          text: "FALLBACK",
          dot: "bg-[#F59E0B]",
          textClass: "text-[#F59E0B]",
        };
      case "UNAVAILABLE":
        return {
          text: "UNAVAILABLE",
          dot: "bg-[#F59E0B]",
          textClass: "text-[#F59E0B]",
        };
      case "NOT_TESTED":
        return {
          text: "NOT TESTED",
          dot: "bg-[#6E7785]",
          textClass: "text-[#9BA7B4]",
        };
      case "IDLE":
      default:
        return {
          text: "IDLE",
          dot: "bg-[#6E7785]",
          textClass: "text-[#6E7785]",
        };
    }
  };

  const handleClick = (step: PipelineStepView) => {
    setActiveDetailStep((prev) => (prev?.key === step.key ? null : step));
    onSelectStep?.(step);
  };

  return (
    <section
      aria-label="Decision Pipeline"
      className="aegis-card rounded-2xl p-5"
    >
      <div className="mb-4 flex flex-wrap items-center justify-between gap-2">
        <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em] text-[#9BA7B4]">
          DECISION PIPELINE
        </span>
        <span className="text-xs text-[#6E7785]">
          End-to-end 7-stage evaluation · Click any stage to inspect raw details
        </span>
      </div>

      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-7">
        {steps.map((step, idx) => {
          const statusMeta = getBottomStatusLabel(step);
          const isSelected =
            selectedStepKey === step.key || activeDetailStep?.key === step.key;

          return (
            <div key={step.key} className="relative flex flex-col">
              <button
                type="button"
                onClick={() => handleClick(step)}
                className={`group flex h-full flex-col justify-between rounded-xl border p-3.5 text-left transition-all duration-200 ${
                  isSelected
                    ? "border-[#4EE1C2]/60 bg-[#1A222B]/90 shadow-[0_0_20px_rgba(78,225,194,0.12)]"
                    : "border-[#2A3542]/80 bg-[#0A0D10]/65 hover:border-[#4EE1C2]/35 hover:bg-[#1A222B]/50"
                }`}
              >
                <div>
                  <div className="flex items-center justify-between gap-1">
                    <span className="font-mono text-xs font-medium text-[#6E7785]">
                      {step.stepNumber}
                    </span>
                    <span className="font-mono text-[10px] text-[#6E7785] truncate">
                      {step.measuredDurationMs !== null
                        ? `${step.measuredDurationMs} ms`
                        : step.key === "VERIFY" && step.status === "SKIPPED"
                        ? "NOT_SENT"
                        : "—"}
                    </span>
                  </div>

                  <div className="mt-2 flex flex-col items-center text-center">
                    <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#2A3542]/80 bg-[#11161D] group-hover:border-[#4EE1C2]/30 transition">
                      {getStepIcon(step.key, step.status)}
                    </div>
                    <div className="mt-2 text-xs font-semibold text-[#E6EDF3]">
                      {SHORT_NAMES[step.key]}
                    </div>
                    <p className="mt-1 text-[11px] leading-snug text-[#9BA7B4] line-clamp-2">
                      {SHORT_DESCRIPTIONS[step.key]}
                    </p>
                  </div>
                </div>

                <div className="mt-3 flex items-center justify-center gap-1.5 border-t border-[#2A3542]/50 pt-2.5">
                  <span
                    className={`h-1.5 w-1.5 rounded-full ${statusMeta.dot}`}
                  />
                  <span
                    className={`font-mono text-[10px] font-semibold tracking-wider ${statusMeta.textClass}`}
                  >
                    {statusMeta.text}
                  </span>
                </div>
              </button>

              {idx < steps.length - 1 && (
                <div className="pointer-events-none absolute -right-2 top-1/2 z-10 hidden -translate-y-1/2 text-[#6E7785]/60 lg:flex">
                  <ArrowRight className="h-3.5 w-3.5" />
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Progressive Disclosure Drawer for Selected Step */}
      {activeDetailStep && (
        <div className="mt-3.5 flex flex-wrap items-start justify-between gap-4 rounded-xl border border-[#4EE1C2]/30 bg-[#0A0D10]/90 p-3.5 text-xs animate-fade-up">
          <div className="space-y-1.5">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-semibold text-[#E6EDF3]">
                {activeDetailStep.title}
              </span>
              <span className="rounded border border-[#2A3542] bg-[#11161D] px-2 py-0.5 font-mono text-[10px] text-[#4EE1C2]">
                {activeDetailStep.verdictBadge}
              </span>
              <span className="rounded border border-[#2A3542]/80 bg-[#1A222B] px-2 py-0.5 font-mono text-[10px] text-[#9BA7B4]">
                status: {activeDetailStep.status}
              </span>
              <span className="font-mono text-[10px] text-[#6E7785]">
                actor: {activeDetailStep.actor} · mode:{" "}
                {activeDetailStep.sourceMode} ·{" "}
                {activeDetailStep.durationDisplay}
              </span>
            </div>
            <p className="text-[#9BA7B4]">{activeDetailStep.summary}</p>
            {activeDetailStep.evidenceId && (
              <div className="flex items-center gap-3 pt-0.5 font-mono text-[11px]">
                <span className="text-[#4EE1C2]">
                  Evidence ID: {activeDetailStep.evidenceId}
                </span>
                <Link
                  href={`/activity?eventId=${activeDetailStep.evidenceId}`}
                  className="text-[#9BA7B4] underline hover:text-[#E6EDF3]"
                >
                  Inspect in Activity Log →
                </Link>
              </div>
            )}
          </div>
          <button
            type="button"
            onClick={() => setActiveDetailStep(null)}
            className="rounded-lg border border-[#2A3542] bg-[#11161D] p-1 text-[#9BA7B4] hover:text-[#E6EDF3]"
            aria-label="Close Stage Details"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}
    </section>
  );
}
