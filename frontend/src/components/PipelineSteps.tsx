"use client";

import React from "react";
import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  Clock,
  Cpu,
  Database,
  Eye,
  ShieldAlert,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import type { PipelineStepView } from "@/lib/view-helpers";

interface PipelineStepsProps {
  steps: PipelineStepView[];
  selectedStepKey?: PipelineStepView["key"] | null;
  onSelectStep?: (step: PipelineStepView) => void;
}

export function PipelineSteps({
  steps,
  selectedStepKey,
  onSelectStep,
}: PipelineStepsProps) {
  const getStepIcon = (key: PipelineStepView["key"]) => {
    switch (key) {
      case "OBSERVE":
        return <Eye className="h-4 w-4" />;
      case "CLASSIFY":
        return <Cpu className="h-4 w-4" />;
      case "REASON":
        return <Terminal className="h-4 w-4" />;
      case "RISK_GATE":
        return <ShieldAlert className="h-4 w-4" />;
      case "ACTION":
        return <ShieldCheck className="h-4 w-4" />;
      case "VERIFY":
        return <CheckCircle2 className="h-4 w-4" />;
      case "AUDIT":
        return <Database className="h-4 w-4" />;
    }
  };

  const getStatusStyles = (status: PipelineStepView["status"]) => {
    switch (status) {
      case "COMPLETED":
        return {
          card: "border-emerald-500/35 bg-emerald-950/20 hover:border-emerald-500/60",
          badge: "bg-emerald-500/20 text-emerald-300 border-emerald-500/40",
          dot: "bg-emerald-400",
        };
      case "VETOED":
        return {
          card: "border-rose-500/45 bg-rose-950/25 hover:border-rose-500/70",
          badge: "bg-rose-500/20 text-rose-300 border-rose-500/40",
          dot: "bg-rose-400",
        };
      case "FALLBACK":
        return {
          card: "border-amber-500/40 bg-amber-950/20 hover:border-amber-500/65",
          badge: "bg-amber-500/20 text-amber-300 border-amber-500/40",
          dot: "bg-amber-400",
        };
      case "IDLE":
        return {
          card: "border-slate-800 bg-slate-900/50 hover:border-slate-700",
          badge: "bg-slate-800 text-slate-400 border-slate-700",
          dot: "bg-slate-500",
        };
    }
  };

  return (
    <section
      aria-label="Autonomous 7-Step Execution Pipeline"
      className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow-lg"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
            1-Screen Autonomous Cycle: Observe → Classify → Reason → Risk Gate → Action/No-Trade → Verify → Audit
          </h2>
          <p className="text-xs text-slate-400">
            Measured durations come directly from ATK subprocess receipts and SQLite event timestamps. Click any stage to inspect its raw evidence ID.
          </p>
        </div>
        <div className="flex items-center gap-3 text-[11px] font-mono text-slate-400">
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-emerald-400" /> PASS / COMPLETED
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-amber-400" /> DECLARED FALLBACK
          </span>
          <span className="inline-flex items-center gap-1">
            <span className="h-2 w-2 rounded-full bg-rose-400" /> DETERMINISTIC VETO
          </span>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-7">
        {steps.map((step, idx) => {
          const style = getStatusStyles(step.status);
          const isSelected = selectedStepKey === step.key;

          return (
            <div key={step.key} className="relative flex flex-col">
              <button
                type="button"
                onClick={() => onSelectStep?.(step)}
                className={`flex h-full flex-col justify-between rounded-lg border p-3 text-left transition ${
                  style.card
                } ${isSelected ? "ring-2 ring-indigo-400" : ""}`}
              >
                <div>
                  <div className="flex items-center justify-between gap-1.5">
                    <span className="inline-flex items-center gap-1.5 text-xs font-bold text-white">
                      {getStepIcon(step.key)}
                      <span>{step.title}</span>
                    </span>
                    <span className={`h-2 w-2 shrink-0 rounded-full ${style.dot}`} />
                  </div>

                  <div className="mt-2">
                    <span
                      className={`inline-block rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold ${style.badge}`}
                    >
                      {step.verdictBadge}
                    </span>
                  </div>

                  <p className="mt-2 text-[11px] leading-relaxed text-slate-300 line-clamp-3">
                    {step.summary}
                  </p>
                </div>

                <div className="mt-3 border-t border-slate-800/80 pt-2 font-mono text-[10px] text-slate-400">
                  <div className="flex items-center justify-between">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="h-3 w-3 text-slate-500" />
                      {step.measuredDurationMs !== null
                        ? `${step.measuredDurationMs} ms`
                        : "— ms"}
                    </span>
                    <span className="uppercase text-slate-500">{step.actor}</span>
                  </div>
                  {step.evidenceId && (
                    <div className="mt-1 truncate text-[9px] text-indigo-300/90">
                      ev:{step.evidenceId.slice(0, 14)}…
                    </div>
                  )}
                </div>
              </button>

              {idx < steps.length - 1 && (
                <div className="hidden lg:flex absolute -right-2 top-1/2 z-10 -translate-y-1/2 text-slate-600 pointer-events-none">
                  <ArrowRight className="h-3.5 w-3.5" />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
}
