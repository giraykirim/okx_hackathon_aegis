"use client";

import React from "react";
import Link from "next/link";
import {
  Ban,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Database,
  Eye,
  FileSpreadsheet,
  FileText,
  Filter,
  Pause,
  Play,
  Shield,
  ShieldAlert,
  User,
  X,
} from "lucide-react";
import { AdminUnlockModal } from "@/components/AdminUnlockModal";
import { HeaderBar } from "@/components/HeaderBar";
import { ProofDrawerModal } from "@/components/ProofDrawerModal";
import {
  RECORDED_EVENTS_MARKET_ONLY,
  RECORDED_MOCK_SCENARIOS,
  RECORDED_SNAPSHOT_MARKET_ONLY,
} from "@/lib/fixtures";
import type { EventItem, Snapshot } from "@/lib/types";

const COMBINED_FIXTURE_EVENTS: EventItem[] = [
  ...RECORDED_EVENTS_MARKET_ONLY,
  ...RECORDED_MOCK_SCENARIOS.unknown_order.events,
  ...RECORDED_MOCK_SCENARIOS.duplicate_intent.events,
  ...RECORDED_MOCK_SCENARIOS.stale_feed.events,
  ...RECORDED_MOCK_SCENARIOS.laya_halt.events,
];

export default function ActivityPage() {
  const [snapshot, setSnapshot] = React.useState<Snapshot>(
    RECORDED_SNAPSHOT_MARKET_ONLY
  );
  const [events, setEvents] = React.useState<EventItem[]>(
    COMBINED_FIXTURE_EVENTS
  );
  const [backendLive, setBackendLive] = React.useState(false);
  const [sseState, setSseState] = React.useState<
    "CONNECTING" | "LIVE" | "FALLBACK" | "DISCONNECTED"
  >("CONNECTING");
  const [streamPaused, setStreamPaused] = React.useState(false);

  // Filters (Reference Set B)
  const [modeFilter, setModeFilter] = React.useState<string>("ALL");
  const [severityFilter, setSeverityFilter] = React.useState<string>("ALL");
  const [typeFilter, setTypeFilter] = React.useState<string>("ALL");

  // Selected event for right-hand detail panel
  const [selectedEventId, setSelectedEventId] = React.useState<string | null>(
    RECORDED_EVENTS_MARKET_ONLY[0]?.id ?? null
  );
  const [expandEvidence, setExpandEvidence] = React.useState(true);
  const [expandRaw, setExpandRaw] = React.useState(false);
  const [expandRelated, setExpandRelated] = React.useState(false);

  const [proofModalOpen, setProofModalOpen] = React.useState(false);
  const [adminModalOpen, setAdminModalOpen] = React.useState(false);
  const [adminSecret, setAdminSecret] = React.useState("");

  // Read optional ?eventId=... query parameter on mount
  React.useEffect(() => {
    if (typeof window === "undefined") return;
    const params = new URLSearchParams(window.location.search);
    const qId = params.get("eventId");
    if (qId) {
      setSelectedEventId(qId);
    }
  }, []);

  const syncFromApi = React.useCallback(async () => {
    try {
      const [snapRes, evRes] = await Promise.all([
        fetch("/api/snapshot", { cache: "no-store" }),
        fetch("/api/events?limit=150", { cache: "no-store" }),
      ]);
      const isLive = snapRes.headers.get("X-AEGIS-Backend-Status") === "LIVE";
      setBackendLive(isLive);

      if (snapRes.ok) {
        setSnapshot((await snapRes.json()) as Snapshot);
      }
      if (evRes.ok) {
        const apiEvents = (await evRes.json()) as EventItem[];
        if (isLive && apiEvents.length > 0) {
          setEvents(apiEvents);
        }
      }
    } catch {
      setBackendLive(false);
    }
  }, []);

  React.useEffect(() => {
    syncFromApi();
  }, [syncFromApi]);

  React.useEffect(() => {
    if (
      streamPaused ||
      typeof window === "undefined" ||
      typeof EventSource === "undefined"
    ) {
      return;
    }

    const es = new EventSource("/api/stream");
    es.onopen = () => setSseState("LIVE");
    const onEvent = (msg: MessageEvent) => {
      try {
        const parsed = JSON.parse(msg.data) as EventItem;
        setEvents((prev) => {
          if (parsed.id && prev.some((e) => e.id === parsed.id)) return prev;
          return [...prev, parsed];
        });
      } catch {
        // ignore
      }
    };
    es.addEventListener("aegis", onEvent);
    es.onerror = () => {
      setSseState("FALLBACK");
      es.close();
    };
    return () => {
      es.removeEventListener("aegis", onEvent);
      es.close();
    };
  }, [streamPaused]);

  const filteredEvents = React.useMemo(() => {
    return events.filter((ev) => {
      if (modeFilter !== "ALL" && ev.source_mode !== modeFilter) return false;
      if (severityFilter !== "ALL" && ev.severity !== severityFilter)
        return false;
      if (typeFilter !== "ALL" && ev.type !== typeFilter) return false;
      return true;
    });
  }, [events, modeFilter, severityFilter, typeFilter]);

  const selectedEvent = React.useMemo(() => {
    if (!selectedEventId) return filteredEvents[0] ?? null;
    return (
      events.find((e) => e.id === selectedEventId) ??
      filteredEvents[0] ??
      null
    );
  }, [events, filteredEvents, selectedEventId]);

  const relatedEvents = React.useMemo(() => {
    if (!selectedEvent) return [];
    return events.filter(
      (e) =>
        e.run_id === selectedEvent.run_id && e.id !== selectedEvent.id
    );
  }, [events, selectedEvent]);

  const getEventVisuals = (type: string) => {
    switch (type) {
      case "ATK_RECEIPT":
        return {
          icon: <FileText className="h-4 w-4 text-[#4EE1C2]" />,
          box: "border-[#4EE1C2]/30 bg-[#4EE1C2]/10",
          dot: "bg-[#4EE1C2]",
          agentName: "Sentinel (ATK)",
          context: "OKX TR Market Subprocess",
        };
      case "OBSERVE":
        return {
          icon: <Eye className="h-4 w-4 text-[#3B82F6]" />,
          box: "border-[#3B82F6]/30 bg-[#3B82F6]/10",
          dot: "bg-[#3B82F6]",
          agentName: "Sentinel",
          context: "Market & Instrument Context",
        };
      case "CLASSIFY":
        return {
          icon: <FileText className="h-4 w-4 text-[#F59E0B]" />,
          box: "border-[#F59E0B]/30 bg-[#F59E0B]/10",
          dot: "bg-[#F59E0B]",
          agentName: "LAYA Classifier",
          context: "Operational Regime Check",
        };
      case "REASON":
        return {
          icon: <Brain className="h-4 w-4 text-[#A855F7]" />,
          box: "border-[#A855F7]/30 bg-[#A855F7]/10",
          dot: "bg-[#A855F7]",
          agentName: "EVREN Reasoner",
          context: "Bounded Proposal Schema",
        };
      case "RISK_GATE":
      case "RISK_CHECK":
        return {
          icon: <Shield className="h-4 w-4 text-[#EF4444]" />,
          box: "border-[#EF4444]/35 bg-[#EF4444]/12",
          dot: "bg-[#EF4444]",
          agentName: "Policy Gate",
          context: "Deterministic Safety Rules",
        };
      case "NO_TRADE":
        return {
          icon: <Ban className="h-4 w-4 text-[#F59E0B]" />,
          box: "border-[#F59E0B]/35 bg-[#F59E0B]/12",
          dot: "bg-[#F59E0B]",
          agentName: "Executor",
          context: "Execution Blocked (NOT_SENT)",
        };
      case "VERIFY":
        return {
          icon: <CheckCircle2 className="h-4 w-4 text-[#4EE1C2]" />,
          box: "border-[#4EE1C2]/30 bg-[#4EE1C2]/10",
          dot: "bg-[#4EE1C2]",
          agentName: "Verifier",
          context: "Venue Reconciliation",
        };
      case "AUDIT":
      default:
        return {
          icon: <FileSpreadsheet className="h-4 w-4 text-[#3B82F6]" />,
          box: "border-[#3B82F6]/30 bg-[#3B82F6]/10",
          dot: "bg-[#3B82F6]",
          agentName: "Guardian",
          context: "Audit Sealed (SQLite)",
        };
    }
  };

  const uniqueTypes = Array.from(new Set(events.map((e) => e.type)));

  return (
    <div className="min-h-screen bg-[#0A0D10] text-[#E6EDF3]">
      <HeaderBar
        sourceMode={snapshot.source_mode}
        running={snapshot.running}
        backendLive={backendLive}
        sseState={sseState}
        lastCycleAt={snapshot.last_cycle_at}
        observedAt={snapshot.observation?.observed_at ?? null}
        onInspectProof={() => setProofModalOpen(true)}
        onOpenAdminModal={() => setAdminModalOpen(true)}
        adminUnlocked={Boolean(adminSecret)}
        onRefresh={syncFromApi}
      />

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6">
        {/* Page Header + Live Stream Indicator (Reference Set B) */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-bold tracking-tight text-[#E6EDF3] sm:text-3xl">
              Activity
            </h1>
            <p className="mt-1 text-sm text-[#9BA7B4]">
              Trace, verify, and audit every step of your agent&apos;s decision process.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="rounded-lg border border-[#2A3542] bg-[#11161D] px-3 py-1.5 font-mono text-xs text-[#9BA7B4]">
              Showing {filteredEvents.length} events
            </span>
            <span className="inline-flex items-center gap-1.5 rounded-lg border border-[#4EE1C2]/35 bg-[#4EE1C2]/10 px-3 py-1.5 font-mono text-xs font-semibold text-[#4EE1C2]">
              <span
                className={`h-2 w-2 rounded-full bg-[#22C55E] ${
                  streamPaused ? "" : "animate-pulse"
                }`}
              />
              {streamPaused ? "Paused" : "Live"}
            </span>
            <button
              type="button"
              onClick={() => setStreamPaused((p) => !p)}
              className="rounded-lg border border-[#2A3542] bg-[#11161D] p-2 text-[#9BA7B4] hover:border-[#4EE1C2]/40 hover:text-[#E6EDF3] transition"
              title={streamPaused ? "Resume SSE stream" : "Pause SSE stream"}
            >
              {streamPaused ? (
                <Play className="h-3.5 w-3.5" />
              ) : (
                <Pause className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
        </div>

        {/* Sub-navigation Tabs (Reference Set B) */}
        <div className="flex items-center gap-6 border-b border-[#2A3542]/70 text-xs font-medium">
          <Link
            href="/"
            className="border-b-2 border-transparent pb-2.5 text-[#9BA7B4] hover:text-[#E6EDF3] transition"
          >
            Overview
          </Link>
          <Link
            href="/activity"
            className="border-b-2 border-[#4EE1C2] pb-2.5 font-semibold text-[#4EE1C2]"
          >
            Activity
          </Link>
          <Link
            href="/avalanche"
            className="border-b-2 border-transparent pb-2.5 text-[#9BA7B4] hover:text-[#E6EDF3] transition"
          >
            On-chain
          </Link>
          <Link
            href="/service"
            className="border-b-2 border-transparent pb-2.5 text-[#9BA7B4] hover:text-[#E6EDF3] transition"
          >
            Risk Service
          </Link>
        </div>

        {/* Main 2-Column Audit Console (Reference Set B) */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-12 lg:items-start">
          {/* Left 8 Cols: Filter Bar + Vertical Timeline */}
          <div className="aegis-card lg:col-span-8 rounded-2xl p-5">
            {/* Filter Row */}
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#2A3542]/80 bg-[#0A0D10]/70 px-3.5 py-2.5 text-xs">
              <div className="flex flex-wrap items-center gap-3">
                {/* Source Mode Filter */}
                <label className="flex items-center gap-2 text-[#9BA7B4]">
                  <Database className="h-3.5 w-3.5 text-[#6E7785]" />
                  <span>Source Mode</span>
                  <select
                    value={modeFilter}
                    onChange={(e) => setModeFilter(e.target.value)}
                    className="rounded-lg border border-[#2A3542] bg-[#11161D] px-2.5 py-1 font-mono text-xs text-[#E6EDF3] focus:border-[#4EE1C2] focus:outline-none"
                  >
                    <option value="ALL">All modes</option>
                    <option value="MARKET_ONLY">MARKET_ONLY</option>
                    <option value="MOCK">MOCK</option>
                  </select>
                </label>

                {/* Severity Filter */}
                <label className="flex items-center gap-2 text-[#9BA7B4]">
                  <Shield className="h-3.5 w-3.5 text-[#6E7785]" />
                  <span>Severity</span>
                  <select
                    value={severityFilter}
                    onChange={(e) => setSeverityFilter(e.target.value)}
                    className="rounded-lg border border-[#2A3542] bg-[#11161D] px-2.5 py-1 font-mono text-xs text-[#E6EDF3] focus:border-[#4EE1C2] focus:outline-none"
                  >
                    <option value="ALL">All levels</option>
                    <option value="INFO">INFO</option>
                    <option value="WARNING">WARNING</option>
                    <option value="ERROR">ERROR</option>
                  </select>
                </label>

                {/* Event Type Filter */}
                <label className="flex items-center gap-2 text-[#9BA7B4]">
                  <Filter className="h-3.5 w-3.5 text-[#6E7785]" />
                  <span>Stage</span>
                  <select
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                    className="rounded-lg border border-[#2A3542] bg-[#11161D] px-2.5 py-1 font-mono text-xs text-[#E6EDF3] focus:border-[#4EE1C2] focus:outline-none"
                  >
                    <option value="ALL">All stages</option>
                    {uniqueTypes.map((t) => (
                      <option key={t} value={t}>
                        {t}
                      </option>
                    ))}
                  </select>
                </label>
              </div>

              {(modeFilter !== "ALL" ||
                severityFilter !== "ALL" ||
                typeFilter !== "ALL") && (
                <button
                  type="button"
                  onClick={() => {
                    setModeFilter("ALL");
                    setSeverityFilter("ALL");
                    setTypeFilter("ALL");
                  }}
                  className="inline-flex items-center gap-1 text-xs text-[#9BA7B4] hover:text-[#4EE1C2] transition"
                >
                  <span>Clear filters</span>
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {/* Vertical Timeline Rows */}
            <div className="relative space-y-2.5">
              {filteredEvents.map((ev, idx) => {
                const vis = getEventVisuals(ev.type);
                const isSelected = selectedEvent?.id === ev.id;
                const timeShort = ev.timestamp
                  ? ev.timestamp.replace("T", " ").slice(11, 19)
                  : "—";

                return (
                  <div
                    key={ev.id || `${ev.run_id}-${ev.type}-${idx}`}
                    className="flex items-center gap-3"
                  >
                    {/* Timestamp + Vertical Connector */}
                    <div className="hidden sm:flex w-20 shrink-0 items-center justify-end gap-2.5 font-mono text-[11px] text-[#6E7785]">
                      <span>{timeShort}</span>
                      <span
                        className={`h-2.5 w-2.5 rounded-full ring-4 ring-[#0A0D10] ${
                          isSelected ? "bg-[#4EE1C2]" : "bg-[#2A3542]"
                        }`}
                      />
                    </div>

                    {/* Event Row Card */}
                    <button
                      type="button"
                      onClick={() => setSelectedEventId(ev.id ?? null)}
                      className={`group flex flex-1 flex-wrap items-center justify-between gap-3 rounded-xl border p-3.5 text-left transition-all ${
                        isSelected
                          ? "border-[#4EE1C2]/65 bg-[#1A222B]/85 shadow-[0_0_24px_rgba(78,225,194,0.1)]"
                          : "border-[#2A3542]/75 bg-[#0A0D10]/65 hover:border-[#4EE1C2]/35 hover:bg-[#1A222B]/40"
                      }`}
                    >
                      <div className="flex items-center gap-3.5 min-w-0 flex-1">
                        <div
                          className={`flex h-9 w-9 shrink-0 items-center justify-center rounded-lg border ${vis.box}`}
                        >
                          {vis.icon}
                        </div>
                        <div className="min-w-0 flex-1">
                          <div className="font-mono text-xs font-bold text-[#E6EDF3]">
                            {ev.type}
                          </div>
                          <div className="mt-0.5 truncate text-xs text-[#9BA7B4]">
                            {ev.message}
                          </div>
                        </div>
                      </div>

                      {/* Metadata Columns (Agent | Source Mode | Context) */}
                      <div className="flex flex-wrap items-center gap-4 text-xs">
                        <div className="hidden md:block w-28">
                          <div className="text-[10px] text-[#6E7785]">Agent</div>
                          <div className="mt-0.5 inline-flex items-center gap-1 font-medium text-[#E6EDF3]">
                            <User className="h-3 w-3 text-[#4EE1C2]" />
                            <span>{ev.actor || vis.agentName}</span>
                          </div>
                        </div>

                        <div className="w-28">
                          <div className="text-[10px] text-[#6E7785]">
                            Source Mode
                          </div>
                          <span
                            className={`mt-0.5 inline-block rounded border px-2 py-0.5 font-mono text-[10px] font-semibold ${
                              ev.source_mode === "MOCK"
                                ? "border-[#F59E0B]/40 bg-[#F59E0B]/10 text-[#F59E0B]"
                                : "border-[#2A3542] bg-[#11161D] text-[#9BA7B4]"
                            }`}
                          >
                            {ev.source_mode}
                          </span>
                        </div>

                        <div className="hidden xl:block w-36">
                          <div className="text-[10px] text-[#6E7785]">
                            Context
                          </div>
                          <div className="mt-0.5 truncate font-medium text-[#E6EDF3]">
                            {vis.context}
                          </div>
                        </div>

                        {ev.severity !== "INFO" && (
                          <span className="flex h-5 w-5 items-center justify-center rounded-full bg-[#EF4444]/20 text-[#EF4444]">
                            <ShieldAlert className="h-3.5 w-3.5" />
                          </span>
                        )}

                        <ChevronRight className="h-4 w-4 text-[#6E7785] group-hover:text-[#4EE1C2] transition" />
                      </div>
                    </button>
                  </div>
                );
              })}
            </div>
          </div>

          {/* Right 4 Cols: Inspector Detail Panel (Reference Set B) */}
          <aside
            aria-label="Selected Event Detail Inspector"
            className="aegis-card lg:col-span-4 sticky top-20 rounded-2xl p-5"
          >
            {selectedEvent ? (
              <div className="space-y-4">
                {/* Header */}
                <div className="flex items-start justify-between gap-3 border-b border-[#2A3542]/70 pb-4">
                  <div className="flex items-center gap-3">
                    <div
                      className={`flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border ${
                        getEventVisuals(selectedEvent.type).box
                      }`}
                    >
                      {getEventVisuals(selectedEvent.type).icon}
                    </div>
                    <div>
                      <h2 className="font-mono text-sm font-bold text-[#E6EDF3]">
                        {selectedEvent.type}
                      </h2>
                      <p className="mt-0.5 text-xs text-[#9BA7B4]">
                        {selectedEvent.message}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Key/Value Metadata Grid */}
                <dl className="space-y-2.5 text-xs border-b border-[#2A3542]/70 pb-4">
                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-[#6E7785]">Timestamp</dt>
                    <dd className="font-mono text-[#E6EDF3]">
                      {selectedEvent.timestamp
                        ? selectedEvent.timestamp
                            .replace("T", " ")
                            .slice(0, 19) + " UTC"
                        : "N/A"}
                    </dd>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-[#6E7785]">Event ID</dt>
                    <dd className="font-mono text-[11px] text-[#E6EDF3] truncate max-w-[200px]">
                      {selectedEvent.id ?? "N/A"}
                    </dd>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-[#6E7785]">Agent / Actor</dt>
                    <dd className="inline-flex items-center gap-1.5 font-medium text-[#4EE1C2]">
                      <User className="h-3.5 w-3.5" />
                      <span>{selectedEvent.actor}</span>
                    </dd>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-[#6E7785]">Source Mode</dt>
                    <dd>
                      <span className="rounded border border-[#2A3542] bg-[#11161D] px-2 py-0.5 font-mono text-[10px] font-semibold text-[#9BA7B4]">
                        {selectedEvent.source_mode}
                      </span>
                    </dd>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-[#6E7785]">Run ID</dt>
                    <dd className="font-mono text-[11px] text-[#9BA7B4]">
                      {selectedEvent.run_id.slice(0, 16)}…
                    </dd>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-[#6E7785]">Severity</dt>
                    <dd className="inline-flex items-center gap-1.5 font-medium">
                      <span
                        className={`h-2 w-2 rounded-full ${
                          selectedEvent.severity === "INFO"
                            ? "bg-[#22C55E]"
                            : selectedEvent.severity === "WARNING"
                            ? "bg-[#F59E0B]"
                            : "bg-[#EF4444]"
                        }`}
                      />
                      <span>{selectedEvent.severity}</span>
                    </dd>
                  </div>

                  {typeof selectedEvent.details?.elapsed_ms === "number" && (
                    <div className="flex items-center justify-between gap-2">
                      <dt className="text-[#6E7785]">Measured Latency</dt>
                      <dd className="font-mono text-[#E6EDF3]">
                        {Number(selectedEvent.details.elapsed_ms).toFixed(2)} ms
                      </dd>
                    </div>
                  )}
                </dl>

                {/* Explanation Box */}
                <div>
                  <div className="text-xs font-medium text-[#9BA7B4]">
                    Explanation
                  </div>
                  <div className="mt-2 rounded-xl border border-[#2A3542] bg-[#0A0D10]/80 p-3 text-xs leading-relaxed text-[#E6EDF3]">
                    {selectedEvent.message}. Recorded under run{" "}
                    <code className="font-mono text-[#4EE1C2]">
                      {selectedEvent.run_id.slice(0, 10)}
                    </code>{" "}
                    in{" "}
                    <code className="font-mono">
                      {selectedEvent.source_mode}
                    </code>{" "}
                    mode.
                  </div>
                </div>

                {/* Expandable Accordion Sections (Reference Set B) */}
                <div className="space-y-2 pt-1">
                  {/* 1. Evidence Accordion */}
                  <div className="rounded-xl border border-[#2A3542]/80 bg-[#0A0D10]/60">
                    <button
                      type="button"
                      onClick={() => setExpandEvidence((p) => !p)}
                      className="flex w-full items-center justify-between px-3.5 py-2.5 text-xs font-medium text-[#E6EDF3]"
                    >
                      <span className="inline-flex items-center gap-2">
                        <FileText className="h-3.5 w-3.5 text-[#4EE1C2]" />
                        <span>Evidence Metadata</span>
                        <span className="rounded-full bg-[#1A222B] px-2 py-0.5 font-mono text-[10px] text-[#9BA7B4]">
                          {Object.keys(selectedEvent.details || {}).length}
                        </span>
                      </span>
                      {expandEvidence ? (
                        <ChevronDown className="h-3.5 w-3.5 text-[#6E7785]" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-[#6E7785]" />
                      )}
                    </button>
                    {expandEvidence && (
                      <div className="border-t border-[#2A3542]/60 px-3.5 py-2.5 font-mono text-[11px] text-[#9BA7B4]">
                        {selectedEvent.details &&
                        Object.keys(selectedEvent.details).length > 0 ? (
                          <div className="space-y-1">
                            {Object.entries(selectedEvent.details).map(
                              ([k, v]) => (
                                <div
                                  key={k}
                                  className="flex items-start justify-between gap-2"
                                >
                                  <span className="text-[#6E7785]">{k}:</span>
                                  <span className="text-right text-[#E6EDF3] break-all">
                                    {typeof v === "object"
                                      ? JSON.stringify(v)
                                      : String(v)}
                                  </span>
                                </div>
                              )
                            )}
                          </div>
                        ) : (
                          <span>No additional structured fields.</span>
                        )}
                      </div>
                    )}
                  </div>

                  {/* 2. Raw Content Accordion */}
                  <div className="rounded-xl border border-[#2A3542]/80 bg-[#0A0D10]/60">
                    <button
                      type="button"
                      onClick={() => setExpandRaw((p) => !p)}
                      className="flex w-full items-center justify-between px-3.5 py-2.5 text-xs font-medium text-[#E6EDF3]"
                    >
                      <span className="inline-flex items-center gap-2">
                        <FileSpreadsheet className="h-3.5 w-3.5 text-[#3B82F6]" />
                        <span>Raw JSON Event</span>
                        <span className="rounded-full bg-[#1A222B] px-2 py-0.5 font-mono text-[10px] text-[#9BA7B4]">
                          1
                        </span>
                      </span>
                      {expandRaw ? (
                        <ChevronDown className="h-3.5 w-3.5 text-[#6E7785]" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-[#6E7785]" />
                      )}
                    </button>
                    {expandRaw && (
                      <pre className="max-h-56 overflow-auto border-t border-[#2A3542]/60 p-3 font-mono text-[10px] text-[#9BA7B4]">
                        {JSON.stringify(selectedEvent, null, 2)}
                      </pre>
                    )}
                  </div>

                  {/* 3. Related Events Accordion */}
                  <div className="rounded-xl border border-[#2A3542]/80 bg-[#0A0D10]/60">
                    <button
                      type="button"
                      onClick={() => setExpandRelated((p) => !p)}
                      className="flex w-full items-center justify-between px-3.5 py-2.5 text-xs font-medium text-[#E6EDF3]"
                    >
                      <span className="inline-flex items-center gap-2">
                        <CheckCircle2 className="h-3.5 w-3.5 text-[#4EE1C2]" />
                        <span>Related Cycle Events</span>
                        <span className="rounded-full bg-[#1A222B] px-2 py-0.5 font-mono text-[10px] text-[#9BA7B4]">
                          {relatedEvents.length}
                        </span>
                      </span>
                      {expandRelated ? (
                        <ChevronDown className="h-3.5 w-3.5 text-[#6E7785]" />
                      ) : (
                        <ChevronRight className="h-3.5 w-3.5 text-[#6E7785]" />
                      )}
                    </button>
                    {expandRelated && (
                      <div className="space-y-1 border-t border-[#2A3542]/60 p-2.5">
                        {relatedEvents.map((rel, i) => (
                          <button
                            key={rel.id || i}
                            type="button"
                            onClick={() => setSelectedEventId(rel.id ?? null)}
                            className="flex w-full items-center justify-between rounded-lg px-2 py-1.5 text-left font-mono text-[11px] text-[#9BA7B4] hover:bg-[#1A222B] hover:text-[#4EE1C2]"
                          >
                            <span>{rel.type}</span>
                            <span className="text-[10px] text-[#6E7785]">
                              {rel.actor}
                            </span>
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            ) : (
              <div className="py-12 text-center text-xs text-[#6E7785]">
                Select any event row on the left to inspect its full provenance.
              </div>
            )}
          </aside>
        </div>
      </main>

      <ProofDrawerModal
        open={proofModalOpen}
        onClose={() => setProofModalOpen(false)}
        snapshot={snapshot}
        events={events}
      />

      <AdminUnlockModal
        open={adminModalOpen}
        onClose={() => setAdminModalOpen(false)}
        adminSecret={adminSecret}
        onSaveSecret={setAdminSecret}
      />
    </div>
  );
}
