"use client";

import React from "react";
import {
  Ban,
  Brain,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  Clock,
  Database,
  Eye,
  FileSpreadsheet,
  FileText,
  Filter,
  FlaskConical,
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

const SCENARIO_RUN_IDS: Record<string, string> = {
  market_only: RECORDED_SNAPSHOT_MARKET_ONLY.run_id,
  stale_feed: RECORDED_MOCK_SCENARIOS.stale_feed.snapshot.run_id,
  unknown_order: RECORDED_MOCK_SCENARIOS.unknown_order.snapshot.run_id,
  duplicate_intent: RECORDED_MOCK_SCENARIOS.duplicate_intent.snapshot.run_id,
  laya_halt: RECORDED_MOCK_SCENARIOS.laya_halt.snapshot.run_id,
};

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

  // Section 8 (P1-3): Complete Filter Set (Scenario, Source Mode, Severity, Time Range, Stage)
  const [scenarioFilter, setScenarioFilter] = React.useState<string>("ALL");
  const [modeFilter, setModeFilter] = React.useState<string>("ALL");
  const [severityFilter, setSeverityFilter] = React.useState<string>("ALL");
  const [timeRangeFilter, setTimeRangeFilter] = React.useState<string>("ALL");
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

  const [nowMs, setNowMs] = React.useState<number>(1792229505000);

  // Read optional ?eventId=... query parameter on mount
  React.useEffect(() => {
    const timer = setTimeout(() => {
      setNowMs(Date.now());
      if (typeof window !== "undefined") {
        const params = new URLSearchParams(window.location.search);
        const qId = params.get("eventId");
        if (qId) {
          setSelectedEventId(qId);
        }
      }
    }, 0);
    return () => clearTimeout(timer);
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
          // Deduplicate by id or timestamp+type+message
          const seen = new Set<string>();
          const deduped: EventItem[] = [];
          for (const ev of apiEvents) {
            const key = ev.id || `${ev.timestamp}-${ev.type}-${ev.message}`;
            if (!seen.has(key)) {
              seen.add(key);
              deduped.push(ev);
            }
          }
          setEvents(deduped);
        }
      }
    } catch {
      setBackendLive(false);
    }
  }, []);

  React.useEffect(() => {
    const timer = setTimeout(() => {
      void syncFromApi();
    }, 0);
    return () => clearTimeout(timer);
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
          const newKey =
            parsed.id || `${parsed.timestamp}-${parsed.type}-${parsed.message}`;
          if (
            prev.some(
              (e) =>
                (e.id || `${e.timestamp}-${e.type}-${e.message}`) === newKey
            )
          ) {
            return prev;
          }
          return [...prev, parsed];
        });
      } catch {
        // ignore malformed frame
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
      if (scenarioFilter !== "ALL") {
        const targetRunId = SCENARIO_RUN_IDS[scenarioFilter];
        if (targetRunId && ev.run_id !== targetRunId) return false;
      }
      if (modeFilter !== "ALL" && ev.source_mode !== modeFilter) return false;
      if (severityFilter !== "ALL" && ev.severity !== severityFilter) {
        return false;
      }
      if (typeFilter !== "ALL" && ev.type !== typeFilter) return false;
      if (timeRangeFilter !== "ALL") {
        const evMs = ev.timestamp ? Date.parse(ev.timestamp) : NaN;
        if (Number.isNaN(evMs)) return false;
        const ageMinutes = Math.max(0, (nowMs - evMs) / 60000);
        if (timeRangeFilter === "15M" && ageMinutes > 15) return false;
        if (timeRangeFilter === "1H" && ageMinutes > 60) return false;
        if (timeRangeFilter === "24H" && ageMinutes > 1440) return false;
      }
      return true;
    });
  }, [
    events,
    scenarioFilter,
    modeFilter,
    severityFilter,
    typeFilter,
    timeRangeFilter,
    nowMs,
  ]);

  // Section 8: Selection State Consistency — only select from visible filteredEvents
  const selectedEvent = React.useMemo(() => {
    if (filteredEvents.length === 0) return null;
    if (!selectedEventId) return filteredEvents[0];
    return (
      filteredEvents.find((e) => e.id === selectedEventId) ?? filteredEvents[0]
    );
  }, [filteredEvents, selectedEventId]);

  const relatedEvents = React.useMemo(() => {
    if (!selectedEvent) return [];
    return events.filter(
      (e) => e.run_id === selectedEvent.run_id && e.id !== selectedEvent.id
    );
  }, [events, selectedEvent]);

  // Section 8 (P1-3): Honest Stream / Replay Status Badge
  const streamStatusBadge = React.useMemo(() => {
    if (streamPaused) {
      return {
        label: "Stream Paused",
        dotClass: "bg-[#6E7785]",
        badgeClass: "border-[#2A3542] bg-[#11161D] text-[#9BA7B4]",
      };
    }
    if (
      modeFilter === "MOCK" ||
      (scenarioFilter !== "ALL" && scenarioFilter !== "market_only")
    ) {
      return {
        label: "Mock Scenario",
        dotClass: "bg-[#F59E0B]",
        badgeClass: "border-[#F59E0B]/40 bg-[#F59E0B]/10 text-[#F59E0B]",
      };
    }
    if (!backendLive) {
      return {
        label: "Historical Replay",
        dotClass: "bg-[#F59E0B]",
        badgeClass: "border-[#F59E0B]/40 bg-[#F59E0B]/10 text-[#F59E0B]",
      };
    }
    if (sseState === "LIVE") {
      return {
        label: "Live Stream",
        dotClass: "bg-[#22C55E] animate-pulse",
        badgeClass: "border-[#4EE1C2]/40 bg-[#4EE1C2]/10 text-[#4EE1C2]",
      };
    }
    return {
      label: "Polling Fallback",
      dotClass: "bg-[#14B8A6]",
      badgeClass: "border-[#14B8A6]/40 bg-[#14B8A6]/10 text-[#14B8A6]",
    };
  }, [streamPaused, modeFilter, scenarioFilter, backendLive, sseState]);

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
      case "TRADE_COURT":
      case "COUNCIL":
        return {
          icon: <Brain className="h-4 w-4 text-[#4EE1C2]" />,
          box: "border-[#4EE1C2]/30 bg-[#4EE1C2]/10",
          dot: "bg-[#4EE1C2]",
          agentName: "TradeCourt Council",
          context: "Multi-Seat Advisory Deliberation",
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
          context: "No Order Submitted (NOT_SENT)",
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
          context: "Audit Recorded (SQLite)",
        };
    }
  };

  const uniqueTypes = Array.from(new Set(events.map((e) => e.type)));
  const hasActiveFilters =
    scenarioFilter !== "ALL" ||
    modeFilter !== "ALL" ||
    severityFilter !== "ALL" ||
    timeRangeFilter !== "ALL" ||
    typeFilter !== "ALL";

  const clearAllFilters = () => {
    setScenarioFilter("ALL");
    setModeFilter("ALL");
    setSeverityFilter("ALL");
    setTimeRangeFilter("ALL");
    setTypeFilter("ALL");
  };

  return (
    <div className="min-h-screen bg-[#0A0D10] text-[#E6EDF3]">
      <HeaderBar
        sourceMode={snapshot.source_mode}
        running={snapshot.running}
        backendLive={backendLive}
        sseState={sseState}
        lastCycleAt={snapshot.last_cycle_at}
        observedAt={snapshot.observation?.observed_at ?? null}
        activeScenario={backendLive ? "live_backend" : "recorded_market_only"}
        onInspectProof={() => setProofModalOpen(true)}
        onOpenAdminModal={() => setAdminModalOpen(true)}
        adminUnlocked={Boolean(adminSecret)}
        onRefresh={syncFromApi}
      />

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6">
        {/* Page Header + Honest Stream / Replay Indicator (Section 8) */}
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-[#9BA7B4]">
              AUDIT CONSOLE
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-[#E6EDF3] sm:text-3xl">
              Activity & Evidence Timeline
            </h1>
            <p className="mt-1 text-sm text-[#9BA7B4]">
              Trace, filter, and inspect every recorded observation, classification, risk check, and audit receipt.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <span className="rounded-lg border border-[#2A3542] bg-[#11161D] px-3 py-1.5 font-mono text-xs text-[#9BA7B4]">
              Showing {filteredEvents.length} of {events.length} events
            </span>
            <span
              className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 font-mono text-xs font-semibold ${streamStatusBadge.badgeClass}`}
            >
              <span
                className={`h-2 w-2 rounded-full ${streamStatusBadge.dotClass}`}
              />
              {streamStatusBadge.label}
            </span>
            <button
              type="button"
              onClick={() => setStreamPaused((p) => !p)}
              className="rounded-lg border border-[#2A3542] bg-[#11161D] p-2 text-[#9BA7B4] hover:border-[#4EE1C2]/40 hover:text-[#E6EDF3] transition"
              title={streamPaused ? "Resume stream" : "Pause stream"}
            >
              {streamPaused ? (
                <Play className="h-3.5 w-3.5" />
              ) : (
                <Pause className="h-3.5 w-3.5" />
              )}
            </button>
          </div>
        </div>

        {/* Main 2-Column Audit Console */}
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-12 lg:items-start">
          {/* Left 8 Cols: Complete Filter Bar + Vertical Timeline */}
          <div className="aegis-card lg:col-span-8 rounded-2xl p-5">
            {/* Filter Row (Section 8: Scenario, Source Mode, Severity, Time Range, Stage) */}
            <div className="mb-5 flex flex-wrap items-center justify-between gap-3 rounded-xl border border-[#2A3542]/80 bg-[#0A0D10]/70 px-3.5 py-2.5 text-xs">
              <div className="flex flex-wrap items-center gap-3">
                {/* 1. Scenario Filter */}
                <label className="flex items-center gap-1.5 text-[#9BA7B4]">
                  <FlaskConical className="h-3.5 w-3.5 text-[#6E7785]" />
                  <span>Scenario</span>
                  <select
                    aria-label="Scenario Filter"
                    value={scenarioFilter}
                    onChange={(e) => setScenarioFilter(e.target.value)}
                    className="rounded-lg border border-[#2A3542] bg-[#11161D] px-2 py-1 font-mono text-xs text-[#E6EDF3] focus:border-[#4EE1C2] focus:outline-none"
                  >
                    <option value="ALL">All scenarios</option>
                    <option value="market_only">
                      Real ATK (MARKET_ONLY)
                    </option>
                    <option value="stale_feed">Mock: Stale Feed</option>
                    <option value="unknown_order">Mock: Unknown Order</option>
                    <option value="duplicate_intent">
                      Mock: Duplicate Intent
                    </option>
                    <option value="laya_halt">Mock: LAYA HALT</option>
                  </select>
                </label>

                {/* 2. Source Mode Filter */}
                <label className="flex items-center gap-1.5 text-[#9BA7B4]">
                  <Database className="h-3.5 w-3.5 text-[#6E7785]" />
                  <span>Source Mode</span>
                  <select
                    aria-label="Source Mode Filter"
                    value={modeFilter}
                    onChange={(e) => setModeFilter(e.target.value)}
                    className="rounded-lg border border-[#2A3542] bg-[#11161D] px-2 py-1 font-mono text-xs text-[#E6EDF3] focus:border-[#4EE1C2] focus:outline-none"
                  >
                    <option value="ALL">All modes</option>
                    <option value="MARKET_ONLY">MARKET_ONLY</option>
                    <option value="MOCK">MOCK</option>
                    <option value="OKX_DEMO">OKX_DEMO</option>
                  </select>
                </label>

                {/* 3. Severity Filter */}
                <label className="flex items-center gap-1.5 text-[#9BA7B4]">
                  <Shield className="h-3.5 w-3.5 text-[#6E7785]" />
                  <span>Severity</span>
                  <select
                    aria-label="Severity Filter"
                    value={severityFilter}
                    onChange={(e) => setSeverityFilter(e.target.value)}
                    className="rounded-lg border border-[#2A3542] bg-[#11161D] px-2 py-1 font-mono text-xs text-[#E6EDF3] focus:border-[#4EE1C2] focus:outline-none"
                  >
                    <option value="ALL">All levels</option>
                    <option value="INFO">INFO</option>
                    <option value="WARNING">WARNING</option>
                    <option value="ERROR">ERROR</option>
                  </select>
                </label>

                {/* 4. Time Range Filter */}
                <label className="flex items-center gap-1.5 text-[#9BA7B4]">
                  <Clock className="h-3.5 w-3.5 text-[#6E7785]" />
                  <span>Time Range</span>
                  <select
                    aria-label="Time Range Filter"
                    value={timeRangeFilter}
                    onChange={(e) => setTimeRangeFilter(e.target.value)}
                    className="rounded-lg border border-[#2A3542] bg-[#11161D] px-2 py-1 font-mono text-xs text-[#E6EDF3] focus:border-[#4EE1C2] focus:outline-none"
                  >
                    <option value="ALL">All recorded</option>
                    <option value="15M">Last 15m</option>
                    <option value="1H">Last 1h</option>
                    <option value="24H">Last 24h</option>
                  </select>
                </label>

                {/* 5. Stage Filter */}
                <label className="flex items-center gap-1.5 text-[#9BA7B4]">
                  <Filter className="h-3.5 w-3.5 text-[#6E7785]" />
                  <span>Stage</span>
                  <select
                    aria-label="Stage Filter"
                    value={typeFilter}
                    onChange={(e) => setTypeFilter(e.target.value)}
                    className="rounded-lg border border-[#2A3542] bg-[#11161D] px-2 py-1 font-mono text-xs text-[#E6EDF3] focus:border-[#4EE1C2] focus:outline-none"
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

              {hasActiveFilters && (
                <button
                  type="button"
                  onClick={clearAllFilters}
                  className="inline-flex items-center gap-1 text-xs text-[#9BA7B4] hover:text-[#4EE1C2] transition"
                >
                  <span>Clear filters</span>
                  <X className="h-3.5 w-3.5" />
                </button>
              )}
            </div>

            {/* Vertical Timeline Rows */}
            {filteredEvents.length === 0 ? (
              <div className="rounded-xl border border-[#2A3542]/70 bg-[#0A0D10]/60 py-12 text-center">
                <p className="text-sm font-medium text-[#E6EDF3]">
                  No events match the active filter criteria.
                </p>
                <p className="mt-1 text-xs text-[#9BA7B4]">
                  Try broadening the Time Range or clearing active filters.
                </p>
                <button
                  type="button"
                  onClick={clearAllFilters}
                  className="mt-3 rounded-lg border border-[#4EE1C2]/40 bg-[#4EE1C2]/10 px-3 py-1.5 text-xs font-semibold text-[#4EE1C2] hover:bg-[#4EE1C2]/20 transition"
                >
                  Reset All Filters
                </button>
              </div>
            ) : (
              <div className="relative space-y-2.5">
                {filteredEvents.map((ev, idx) => {
                  const vis = getEventVisuals(ev.type);
                  const isSelected = selectedEvent?.id === ev.id;
                  const timeShort = ev.timestamp
                    ? ev.timestamp.replace("T", " ").slice(11, 19)
                    : "Not recorded";

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
                              {ev.message || "Not recorded"}
                            </div>
                          </div>
                        </div>

                        {/* Metadata Columns (Agent | Source Mode | Context) */}
                        <div className="flex flex-wrap items-center gap-4 text-xs">
                          <div className="hidden md:block w-28">
                            <div className="text-[10px] text-[#6E7785]">
                              Agent
                            </div>
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
                              {ev.source_mode || "Unavailable"}
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
            )}
          </div>

          {/* Right 4 Cols: Inspector Detail Panel */}
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
                        {selectedEvent.message || "Not recorded"}
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
                        : "Not recorded"}
                    </dd>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-[#6E7785]">Event ID</dt>
                    <dd className="font-mono text-[11px] text-[#E6EDF3] truncate max-w-[200px]">
                      {selectedEvent.id ?? "Not recorded"}
                    </dd>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-[#6E7785]">Agent / Actor</dt>
                    <dd className="inline-flex items-center gap-1.5 font-medium text-[#4EE1C2]">
                      <User className="h-3.5 w-3.5" />
                      <span>{selectedEvent.actor || "Unavailable"}</span>
                    </dd>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-[#6E7785]">Source Mode</dt>
                    <dd>
                      <span className="rounded border border-[#2A3542] bg-[#11161D] px-2 py-0.5 font-mono text-[10px] font-semibold text-[#9BA7B4]">
                        {selectedEvent.source_mode || "Unavailable"}
                      </span>
                    </dd>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-[#6E7785]">Run ID</dt>
                    <dd className="font-mono text-[11px] text-[#9BA7B4]">
                      {selectedEvent.run_id
                        ? `${selectedEvent.run_id.slice(0, 16)}…`
                        : "Not recorded"}
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
                      <span>{selectedEvent.severity || "INFO"}</span>
                    </dd>
                  </div>

                  <div className="flex items-center justify-between gap-2">
                    <dt className="text-[#6E7785]">Measured Latency</dt>
                    <dd className="font-mono text-[#E6EDF3]">
                      {typeof selectedEvent.details?.elapsed_ms === "number" &&
                      selectedEvent.details.elapsed_ms > 0
                        ? `${Number(selectedEvent.details.elapsed_ms).toFixed(2)} ms`
                        : typeof selectedEvent.details?.duration_ms ===
                            "number" &&
                          selectedEvent.details.duration_ms > 0
                        ? `${Number(selectedEvent.details.duration_ms).toFixed(2)} ms`
                        : "Not measured"}
                    </dd>
                  </div>
                </dl>

                {/* Explanation Box */}
                <div>
                  <div className="text-xs font-medium text-[#9BA7B4]">
                    Explanation
                  </div>
                  <div className="mt-2 rounded-xl border border-[#2A3542] bg-[#0A0D10]/80 p-3 text-xs leading-relaxed text-[#E6EDF3]">
                    {selectedEvent.message || "Event recorded"}. Recorded under
                    run{" "}
                    <code className="font-mono text-[#4EE1C2]">
                      {selectedEvent.run_id
                        ? selectedEvent.run_id.slice(0, 10)
                        : "N/A"}
                    </code>{" "}
                    in{" "}
                    <code className="font-mono">
                      {selectedEvent.source_mode || "MARKET_ONLY"}
                    </code>{" "}
                    mode.
                  </div>
                </div>

                {/* Expandable Accordion Sections */}
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
                                    {v === null || v === undefined
                                      ? "Not recorded"
                                      : typeof v === "object"
                                      ? JSON.stringify(v)
                                      : String(v)}
                                  </span>
                                </div>
                              )
                            )}
                          </div>
                        ) : (
                          <span>Not recorded</span>
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
                No matching event selected. Adjust filters on the left to inspect events.
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
