"use client";

import React from "react";
import { useRouter } from "next/navigation";
import { AdminUnlockModal } from "@/components/AdminUnlockModal";
import { AnimatedMetricCards } from "@/components/AnimatedMetricCards";
import { HeaderBar } from "@/components/HeaderBar";
import { HeroDecisionCard } from "@/components/HeroDecisionCard";
import { OverviewBottomPanels } from "@/components/OverviewBottomPanels";
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
  const router = useRouter();
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
      setSseState("FALLBACK");
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
  };

  const handleInspectEvidenceId = (id: string) => {
    router.push(`/activity?eventId=${id}`);
  };

  const displayTime = snapshot.last_cycle_at
    ? snapshot.last_cycle_at.replace("T", " ").slice(0, 19) + " UTC"
    : "2026-10-17 11:39:35 UTC";

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
        onStartAgent={handleStartAgent}
        onStopAgent={handleStopAgent}
        controlBusy={controlBusy}
        onRefresh={syncFromApi}
      />

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6">
        {controlError && (
          <div className="flex items-center justify-between rounded-xl border border-[#EF4444]/40 bg-[#EF4444]/10 px-4 py-2.5 font-mono text-xs text-[#EF4444]">
            <span>Operator Control Error: {controlError}</span>
            <button
              type="button"
              onClick={() => setControlError(null)}
              className="underline hover:text-[#E6EDF3]"
            >
              Dismiss
            </button>
          </div>
        )}

        {/* Overview Hero Header (Reference Set A) */}
        <div className="flex flex-col justify-between gap-3 sm:flex-row sm:items-end">
          <div>
            <div className="font-mono text-[11px] font-semibold uppercase tracking-[0.18em] text-[#9BA7B4]">
              OVERVIEW
            </div>
            <h1 className="mt-1 text-2xl font-bold tracking-tight text-[#E6EDF3] sm:text-3xl">
              AI-Powered Pre-Trade Risk Monitoring
            </h1>
            <p className="mt-1 text-sm text-[#9BA7B4]">
              Observing markets. Evaluating opportunities. Enforcing deterministic risk policies. Always on your side.
            </p>
          </div>

          <div className="flex items-center gap-3 font-mono text-xs text-[#9BA7B4]">
            <span>{displayTime}</span>
            <span className="inline-flex items-center gap-1.5 font-medium text-[#4EE1C2]">
              <span className="h-2 w-2 rounded-full bg-[#22C55E] animate-pulse" />
              {backendLive
                ? "System Online (Live FastAPI)"
                : "Monitoring Ready (Verified Evidence)"}
            </span>
          </div>
        </div>

        {/* Segmented Scenario Switcher */}
        <ScenarioSwitcher
          activePreset={activePreset}
          onSelectPreset={handleSelectPreset}
          adminUnlocked={Boolean(adminSecret)}
          backendSourceMode={snapshot.source_mode}
          onTriggerLiveMockScenario={handleTriggerLiveMockScenario}
          busy={controlBusy}
        />

        {/* Hero Latest Decision Card (Reference Set A) */}
        <HeroDecisionCard
          decision={snapshot.latest_decision}
          classification={snapshot.classification}
          observation={snapshot.observation}
          onInspectEvidenceId={handleInspectEvidenceId}
        />

        {/* Compact 7-Stage Decision Pipeline (Reference Set A) */}
        <PipelineSteps
          steps={pipelineSteps}
          selectedStepKey={selectedStepKey}
          onSelectStep={handleSelectStep}
        />

        {/* 4 Animated Metric Cards with Sparklines (Reference Set A & D) */}
        <AnimatedMetricCards
          metrics={metrics}
          eventsCount={events.length}
          sourceMode={snapshot.source_mode}
        />

        {/* Latest Activity Preview + System Status Panel (Reference Set A) */}
        <OverviewBottomPanels
          events={events}
          capabilities={snapshot.capabilities}
          runId={snapshot.run_id}
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
