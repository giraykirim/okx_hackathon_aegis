"use client";

import React from "react";
import Link from "next/link";
import { ArrowUpRight, Cpu, ShieldCheck } from "lucide-react";
import { AdminUnlockModal } from "@/components/AdminUnlockModal";
import { EventTimelineAndCapabilities } from "@/components/EventTimelineAndCapabilities";
import { ExplainableVerdictCard } from "@/components/ExplainableVerdictCard";
import { HeaderBar } from "@/components/HeaderBar";
import { PipelineSteps } from "@/components/PipelineSteps";
import { ProofDrawerModal } from "@/components/ProofDrawerModal";
import {
  type DemoPresetKey,
  ScenarioSwitcher,
} from "@/components/ScenarioSwitcher";
import {
  RECORDED_EVENTS_MARKET_ONLY,
  RECORDED_METRICS_MARKET_ONLY,
  RECORDED_MOCK_SCENARIOS,
  RECORDED_SNAPSHOT_MARKET_ONLY,
} from "@/lib/fixtures";
import type { EventItem, Metrics, Snapshot } from "@/lib/types";
import { buildPipelineSteps, type PipelineStepView } from "@/lib/view-helpers";

export default function DashboardPage() {
  const [snapshot, setSnapshot] = React.useState<Snapshot>(
    RECORDED_SNAPSHOT_MARKET_ONLY
  );
  const [events, setEvents] = React.useState<EventItem[]>(
    RECORDED_EVENTS_MARKET_ONLY
  );
  const [metrics, setMetrics] = React.useState<Metrics | null>(
    RECORDED_METRICS_MARKET_ONLY
  );
  const [backendLive, setBackendLive] = React.useState<boolean>(false);
  const [sseState, setSseState] = React.useState<
    "CONNECTING" | "LIVE" | "FALLBACK" | "DISCONNECTED"
  >("CONNECTING");

  const [activePreset, setActivePreset] =
    React.useState<DemoPresetKey>("real_atk_no_trade");
  const [selectedStepKey, setSelectedStepKey] = React.useState<
    PipelineStepView["key"] | null
  >(null);
  const [highlightedEventId, setHighlightedEventId] = React.useState<
    string | null
  >(null);

  const [proofModalOpen, setProofModalOpen] = React.useState(false);
  const [adminModalOpen, setAdminModalOpen] = React.useState(false);
  const [adminSecret, setAdminSecret] = React.useState("");
  const [controlBusy, setControlBusy] = React.useState(false);
  const [controlError, setControlError] = React.useState<string | null>(null);

  const syncFromApi = React.useCallback(async () => {
    try {
      const [snapRes, evRes, metRes] = await Promise.all([
        fetch("/api/snapshot", { cache: "no-store" }),
        fetch("/api/events?limit=100", { cache: "no-store" }),
        fetch("/api/metrics", { cache: "no-store" }),
      ]);

      const isLive = snapRes.headers.get("X-AEGIS-Backend-Status") === "LIVE";
      setBackendLive(isLive);

      if (snapRes.ok) {
        const snapData = (await snapRes.json()) as Snapshot;
        if (activePreset === "real_atk_no_trade" || isLive) {
          setSnapshot(snapData);
        }
      }
      if (evRes.ok) {
        const evData = (await evRes.json()) as EventItem[];
        if (activePreset === "real_atk_no_trade" || isLive) {
          setEvents(evData);
        }
      }
      if (metRes.ok) {
        const metData = (await metRes.json()) as Metrics;
        setMetrics(metData);
      }
    } catch {
      setBackendLive(false);
    }
  }, [activePreset]);

  // Initial fetch + periodic poll fallback
  React.useEffect(() => {
    syncFromApi();
    const timer = setInterval(() => {
      if (activePreset === "real_atk_no_trade") {
        syncFromApi();
      }
    }, 6000);
    return () => clearInterval(timer);
  }, [syncFromApi, activePreset]);

  // SSE subscription (`/api/stream` emitting `event: aegis`)
  React.useEffect(() => {
    if (typeof window === "undefined" || typeof EventSource === "undefined") {
      return;
    }

    const es = new EventSource("/api/stream");

    es.onopen = () => {
      setSseState((prev) => (prev === "CONNECTING" ? "LIVE" : prev));
    };

    const handleAegisEvent = (msg: MessageEvent) => {
      try {
        const parsed = JSON.parse(msg.data) as EventItem;
        setEvents((prev) => {
          if (parsed.id && prev.some((e) => e.id === parsed.id)) {
            return prev;
          }
          return [...prev.slice(-199), parsed];
        });
      } catch {
        // Ignore malformed frame
      }
    };

    es.addEventListener("aegis", handleAegisEvent);

    es.onerror = () => {
      setSseState((prev) => (prev === "LIVE" ? "FALLBACK" : "FALLBACK"));
      es.close();
    };

    return () => {
      es.removeEventListener("aegis", handleAegisEvent);
      es.close();
    };
  }, []);

  const handleSelectPreset = (preset: DemoPresetKey) => {
    setActivePreset(preset);
    setSelectedStepKey(null);
    setHighlightedEventId(null);

    if (preset === "real_atk_no_trade") {
      setSnapshot(RECORDED_SNAPSHOT_MARKET_ONLY);
      setEvents(RECORDED_EVENTS_MARKET_ONLY);
      syncFromApi();
      return;
    }

    const mapKey: Record<
      Exclude<DemoPresetKey, "real_atk_no_trade">,
      keyof typeof RECORDED_MOCK_SCENARIOS
    > = {
      mock_stale_feed: "stale_feed",
      mock_unknown_order: "unknown_order",
      mock_duplicate_intent: "duplicate_intent",
      mock_laya_halt: "laya_halt",
    };
    const chosen = RECORDED_MOCK_SCENARIOS[mapKey[preset]];
    setSnapshot(chosen.snapshot);
    setEvents(chosen.events);
  };

  const handleStartAgent = async () => {
    if (!adminSecret) {
      setAdminModalOpen(true);
      return;
    }
    setControlBusy(true);
    setControlError(null);
    try {
      const res = await fetch("/api/agent/start", {
        method: "POST",
        headers: {
          "X-AEGIS-Admin-Secret": adminSecret,
        },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        setControlError(err.detail || `HTTP ${res.status}`);
      } else {
        await syncFromApi();
      }
    } catch (e) {
      setControlError(e instanceof Error ? e.message : "Network error");
    } finally {
      setControlBusy(false);
    }
  };

  const handleStopAgent = async () => {
    if (!adminSecret) {
      setAdminModalOpen(true);
      return;
    }
    setControlBusy(true);
    setControlError(null);
    try {
      const res = await fetch("/api/agent/stop", {
        method: "POST",
        headers: {
          "X-AEGIS-Admin-Secret": adminSecret,
        },
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Request failed" }));
        setControlError(err.detail || `HTTP ${res.status}`);
      } else {
        await syncFromApi();
      }
    } catch (e) {
      setControlError(e instanceof Error ? e.message : "Network error");
    } finally {
      setControlBusy(false);
    }
  };

  const handleTriggerLiveMockScenario = async (
    scenario: "stale_feed" | "unknown_order" | "duplicate_intent" | "laya_halt"
  ) => {
    if (!adminSecret) {
      setAdminModalOpen(true);
      return;
    }
    setControlBusy(true);
    setControlError(null);
    try {
      const res = await fetch("/api/demo/scenario", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-AEGIS-Admin-Secret": adminSecret,
        },
        body: JSON.stringify({ scenario }),
      });
      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Scenario failed" }));
        setControlError(err.detail || `HTTP ${res.status}`);
      } else {
        await syncFromApi();
      }
    } catch (e) {
      setControlError(e instanceof Error ? e.message : "Network error");
    } finally {
      setControlBusy(false);
    }
  };

  const pipelineSteps = React.useMemo(
    () => buildPipelineSteps(snapshot, events),
    [snapshot, events]
  );

  const handleSelectStep = (step: PipelineStepView) => {
    setSelectedStepKey(step.key);
    if (step.evidenceId) {
      setHighlightedEventId(step.evidenceId);
      const el = document.getElementById(`event-${step.evidenceId}`);
      if (el) {
        el.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }
    }
  };

  const handleInspectEvidenceId = (id: string) => {
    setHighlightedEventId(id);
    const el = document.getElementById(`event-${id}`);
    if (el) {
      el.scrollIntoView({ behavior: "smooth", block: "nearest" });
    }
  };

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
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
        onStartAgent={handleStartAgent}
        onStopAgent={handleStopAgent}
        controlBusy={controlBusy}
        onRefresh={syncFromApi}
      />

      <main className="mx-auto max-w-7xl space-y-4 px-4 py-5">
        {controlError && (
          <div className="flex items-center justify-between rounded-lg border border-rose-500/40 bg-rose-950/30 px-4 py-2.5 font-mono text-xs text-rose-200">
            <span>Operator Control Error: {controlError}</span>
            <button
              type="button"
              onClick={() => setControlError(null)}
              className="underline hover:text-white"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Quick Jury Pitch & Navigation Strip */}
        <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-slate-800 bg-slate-900/50 p-3.5">
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] font-bold uppercase text-emerald-400">
                1. OKX Agent Trade Kit (ATK)
              </span>
              <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
                PASS (MARKET_ONLY)
              </span>
            </div>
            <p className="mt-1 text-xs text-slate-300">
              Real Node subprocess execution of <code className="font-mono">@okx_ai/okx-trade-cli@1.4.8</code> (`site=tr`) with SHA-256 stdout digests.
            </p>
          </div>

          <Link
            href="/service"
            className="group rounded-xl border border-slate-800 bg-slate-900/50 p-3.5 hover:border-indigo-500/50 transition"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] font-bold uppercase text-indigo-400">
                2. B2B Risk Check Service (`/api/v1/risk/evaluate`)
              </span>
              <ArrowUpRight className="h-4 w-4 text-slate-400 group-hover:text-indigo-300" />
            </div>
            <p className="mt-1 text-xs text-slate-300">
              External pre-trade operational evaluation (`order_permission=false`). OKX.AI compatible — <strong className="text-amber-300">NOT_LISTED</strong>.
            </p>
          </Link>

          <Link
            href="/avalanche"
            className="group rounded-xl border border-slate-800 bg-slate-900/50 p-3.5 hover:border-sky-500/50 transition"
          >
            <div className="flex items-center justify-between">
              <span className="font-mono text-[11px] font-bold uppercase text-sky-400">
                3. Avalanche Fuji (Chain 43113)
              </span>
              <ArrowUpRight className="h-4 w-4 text-slate-400 group-hover:text-sky-300" />
            </div>
            <p className="mt-1 text-xs text-slate-300">
              ERC-8004 identity registration & <code className="font-mono">RiskDecisionRegistry</code> SHA-256 receipt verifier (off-chain runtime).
            </p>
          </Link>
        </div>

        {/* Scenario Switcher: Real ATK Market vs Synthetic Unsafe Veto */}
        <ScenarioSwitcher
          activePreset={activePreset}
          onSelectPreset={handleSelectPreset}
          adminUnlocked={Boolean(adminSecret)}
          backendSourceMode={snapshot.source_mode}
          onTriggerLiveMockScenario={handleTriggerLiveMockScenario}
          busy={controlBusy}
        />

        {/* 1-Screen Story: 7-Step Pipeline */}
        <PipelineSteps
          steps={pipelineSteps}
          selectedStepKey={selectedStepKey}
          onSelectStep={handleSelectStep}
        />

        {/* Explainable Result Card */}
        <ExplainableVerdictCard
          decision={snapshot.latest_decision}
          classification={snapshot.classification}
          observation={snapshot.observation}
          onInspectEvidenceId={handleInspectEvidenceId}
        />

        {/* Live Event Timeline + Capabilities + Metrics */}
        <EventTimelineAndCapabilities
          events={events}
          capabilities={snapshot.capabilities}
          metrics={metrics}
          highlightedEventId={highlightedEventId}
        />
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
        statusMessage={controlError}
      />
    </div>
  );
}
