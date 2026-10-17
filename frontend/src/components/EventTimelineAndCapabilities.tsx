"use client";

import React from "react";
import {
  ChevronDown,
  ChevronRight,
  Radio,
} from "lucide-react";
import type { Capability, EventItem, Metrics } from "@/lib/types";

interface EventTimelineAndCapabilitiesProps {
  events: EventItem[];
  capabilities: Record<string, Capability>;
  metrics: Metrics | null;
  highlightedEventId?: string | null;
  onSelectEvent?: (ev: EventItem) => void;
}

export function EventTimelineAndCapabilities({
  events,
  capabilities,
  metrics,
  highlightedEventId,
  onSelectEvent,
}: EventTimelineAndCapabilitiesProps) {
  const [expandedEventIds, setExpandedEventIds] = React.useState<Record<string, boolean>>({});

  const toggleExpand = (id: string) => {
    setExpandedEventIds((prev) => ({ ...prev, [id]: !prev[id] }));
  };

  const getSeverityBadge = (sev: EventItem["severity"]) => {
    switch (sev) {
      case "INFO":
        return "bg-sky-500/15 text-sky-300 border-sky-500/30";
      case "WARNING":
        return "bg-amber-500/15 text-amber-300 border-amber-500/40";
      case "ERROR":
        return "bg-rose-500/15 text-rose-300 border-rose-500/40";
    }
  };

  const getCapabilityBadge = (status: Capability["status"]) => {
    switch (status) {
      case "PASS":
        return "bg-emerald-500/20 text-emerald-300 border-emerald-500/40";
      case "FAIL":
        return "bg-rose-500/20 text-rose-300 border-rose-500/40";
      case "NOT_TESTED":
        return "bg-slate-800 text-slate-300 border-slate-700";
    }
  };

  return (
    <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
      {/* Left 7 Cols: Live Event Timeline (SSE + SQLite Replay) */}
      <section
        aria-label="Live Audit Event Timeline"
        className="lg:col-span-7 flex flex-col rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow-lg"
      >
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2.5">
          <div className="flex items-center gap-2">
            <Radio className="h-4 w-4 text-emerald-400" />
            <h3 className="text-sm font-bold text-white">
              Audit Event Timeline (`/api/events` + `/api/stream` SSE)
            </h3>
          </div>
          <span className="font-mono text-xs text-slate-400">
            Showing {events.length} persisted events (oldest → newest)
          </span>
        </div>

        <div className="max-h-[420px] space-y-2 overflow-y-auto pr-1">
          {events.length === 0 ? (
            <div className="rounded-lg border border-slate-800 bg-slate-950/60 p-4 text-center text-xs text-slate-400">
              No events in current buffer.
            </div>
          ) : (
            events.map((ev, idx) => {
              const evKey = ev.id || `${ev.run_id}-${ev.type}-${idx}`;
              const isHighlighted = Boolean(ev.id && ev.id === highlightedEventId);
              const isExpanded = Boolean(expandedEventIds[evKey] || isHighlighted);

              return (
                <div
                  key={evKey}
                  id={ev.id ? `event-${ev.id}` : undefined}
                  className={`rounded-lg border p-3 transition ${
                    isHighlighted
                      ? "border-indigo-400 bg-indigo-950/30 ring-1 ring-indigo-400"
                      : "border-slate-800/90 bg-slate-950/60 hover:border-slate-700"
                  }`}
                >
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex flex-wrap items-center gap-2">
                      <button
                        type="button"
                        onClick={() => {
                          toggleExpand(evKey);
                          onSelectEvent?.(ev);
                        }}
                        className="inline-flex items-center gap-1 font-mono text-xs font-bold text-white hover:text-indigo-300"
                      >
                        {isExpanded ? (
                          <ChevronDown className="h-3.5 w-3.5 text-slate-400" />
                        ) : (
                          <ChevronRight className="h-3.5 w-3.5 text-slate-400" />
                        )}
                        <span>{ev.type}</span>
                      </button>

                      <span
                        className={`rounded border px-1.5 py-0.5 font-mono text-[10px] font-semibold ${getSeverityBadge(
                          ev.severity
                        )}`}
                      >
                        {ev.severity}
                      </span>

                      <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] text-slate-300">
                        actor:{ev.actor}
                      </span>

                      <span
                        className={`rounded px-1.5 py-0.5 font-mono text-[10px] font-semibold ${
                          ev.source_mode === "MOCK"
                            ? "bg-amber-500/20 text-amber-300"
                            : "bg-emerald-500/20 text-emerald-300"
                        }`}
                      >
                        {ev.source_mode}
                      </span>
                    </div>

                    <div className="flex items-center gap-2 font-mono text-[11px] text-slate-400">
                      {ev.id && (
                        <span className="text-indigo-300/90" title={ev.id}>
                          id:{ev.id.slice(0, 10)}…
                        </span>
                      )}
                      <span>
                        {ev.timestamp
                          ? ev.timestamp.replace("T", " ").slice(11, 23) + "Z"
                          : ""}
                      </span>
                    </div>
                  </div>

                  <p className="mt-1.5 text-xs text-slate-200">{ev.message}</p>

                  {isExpanded && ev.details && Object.keys(ev.details).length > 0 && (
                    <pre className="mt-2 overflow-x-auto rounded border border-slate-800 bg-slate-900/90 p-2.5 font-mono text-[11px] text-slate-300">
                      {JSON.stringify(ev.details, null, 2)}
                    </pre>
                  )}
                </div>
              );
            })
          )}
        </div>
      </section>

      {/* Right 5 Cols: Capabilities Matrix + Audit Metrics */}
      <div className="lg:col-span-5 flex flex-col gap-4">
        {/* Audit-Derived Metrics (`/api/metrics`) */}
        <section
          aria-label="Audit-Derived Metrics"
          className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow-lg"
        >
          <div className="mb-3 flex items-center justify-between border-b border-slate-800 pb-2">
            <h3 className="text-sm font-bold text-white">
              Audit-Derived Metrics (`/api/metrics`)
            </h3>
            <span className="font-mono text-[11px] text-slate-400">
              No synthetic PnL
            </span>
          </div>

          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3">
            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-2.5">
              <div className="text-[11px] text-slate-400">Total Decisions</div>
              <div className="mt-1 font-mono text-lg font-bold text-white">
                {metrics ? metrics.decisions : "—"}
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-2.5">
              <div className="text-[11px] text-slate-400">Policy Vetoed</div>
              <div className="mt-1 font-mono text-lg font-bold text-rose-400">
                {metrics ? metrics.vetoed : "—"}
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-2.5">
              <div className="text-[11px] text-slate-400">Verified Exchange</div>
              <div className="mt-1 font-mono text-lg font-bold text-emerald-400">
                {metrics ? metrics.verified_exchange_orders : "0"}
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-2.5">
              <div className="text-[11px] text-slate-400">MOCK Executions</div>
              <div className="mt-1 font-mono text-lg font-bold text-amber-300">
                {metrics ? metrics.mock_executions : "0"}
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-2.5">
              <div className="text-[11px] text-slate-400">Unresolved Orders</div>
              <div className="mt-1 font-mono text-lg font-bold text-slate-200">
                {metrics ? metrics.unresolved_orders : "0"}
              </div>
            </div>
            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-2.5">
              <div className="text-[11px] text-slate-400">Realized PnL</div>
              <div
                className="mt-1 font-mono text-sm font-bold text-slate-400"
                title="Metrics deliberately report pnl=null; no profit claims"
              >
                null (NOT_TESTED)
              </div>
            </div>
          </div>
        </section>

        {/* System Capabilities (`/api/capabilities`) */}
        <section
          aria-label="System Capabilities Truthfulness"
          className="flex-1 rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow-lg"
        >
          <div className="mb-3 flex items-center justify-between border-b border-slate-800 pb-2">
            <h3 className="text-sm font-bold text-white">
              Integration Capabilities (`/api/capabilities`)
            </h3>
            <span className="font-mono text-[10px] text-slate-400">
              PASS = adapter response observed
            </span>
          </div>

          <div className="space-y-2">
            {Object.entries(capabilities).map(([key, cap]) => (
              <div
                key={key}
                className="rounded-lg border border-slate-800 bg-slate-950/60 p-2.5"
              >
                <div className="flex items-center justify-between">
                  <span className="font-mono text-xs font-bold text-white">
                    {key}
                  </span>
                  <span
                    className={`rounded border px-2 py-0.5 font-mono text-[10px] font-bold ${getCapabilityBadge(
                      cap.status
                    )}`}
                  >
                    {cap.status}
                  </span>
                </div>
                {cap.evidence && cap.evidence.length > 0 ? (
                  <ul className="mt-1.5 space-y-0.5 font-mono text-[11px] text-slate-300">
                    {cap.evidence.map((line, i) => (
                      <li key={i} className="truncate">
                        • {line}
                      </li>
                    ))}
                  </ul>
                ) : (
                  <p className="mt-1 text-[11px] text-slate-500">
                    Not yet verified in live runtime (`status={cap.status}`).
                  </p>
                )}
              </div>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}
