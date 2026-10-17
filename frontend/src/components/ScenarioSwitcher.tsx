"use client";

import React from "react";
import {
  AlertTriangle,
  CheckCircle2,
  FlaskConical,
  Play,
  Radio,
  ShieldAlert,
} from "lucide-react";

export type DemoPresetKey =
  | "real_atk_no_trade"
  | "mock_stale_feed"
  | "mock_unknown_order"
  | "mock_duplicate_intent"
  | "mock_laya_halt";

interface ScenarioSwitcherProps {
  activePreset: DemoPresetKey;
  onSelectPreset: (preset: DemoPresetKey) => void;
  adminUnlocked: boolean;
  backendSourceMode: string;
  onTriggerLiveMockScenario?: (
    scenario: "stale_feed" | "unknown_order" | "duplicate_intent" | "laya_halt"
  ) => void;
  busy?: boolean;
}

export function ScenarioSwitcher({
  activePreset,
  onSelectPreset,
  adminUnlocked,
  backendSourceMode,
  onTriggerLiveMockScenario,
  busy,
}: ScenarioSwitcherProps) {
  return (
    <section
      aria-label="Jury Demo Scenarios"
      className="rounded-xl border border-slate-800 bg-slate-900/60 p-4 shadow-lg"
    >
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-200">
            Two Jury Demo Scenarios: Real ATK Market vs Synthetic Unsafe Veto
          </h2>
          <p className="text-xs text-slate-400">
            Compare (1) Real official OKX ATK market observation (`MARKET_ONLY` → `NO_TRADE`) against (2) Synthetic unsafe states (`MOCK SCENARIO` → deterministic `HALT` / `NOT_SENT`).
          </p>
        </div>
        <span className="rounded border border-slate-700 bg-slate-950 px-2.5 py-1 font-mono text-[11px] text-slate-300">
          Optional Exchange Demo Order:{" "}
          <strong className="text-amber-300">NOT_TESTED (Zero Exchange Writes)</strong>
        </span>
      </div>

      <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">
        {/* Scenario 1: REAL ATK MARKET -> NO_TRADE */}
        <div
          className={`flex flex-col justify-between rounded-lg border p-4 transition ${
            activePreset === "real_atk_no_trade"
              ? "border-emerald-500/60 bg-emerald-950/25 ring-1 ring-emerald-500/40"
              : "border-slate-800 bg-slate-950/60 hover:border-slate-700"
          }`}
        >
          <div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="inline-flex items-center gap-1.5 rounded bg-emerald-500/20 px-2.5 py-0.5 font-mono text-xs font-bold text-emerald-300 border border-emerald-500/40">
                <Radio className="h-3.5 w-3.5" />
                SCENARIO 1: REAL ATK MARKET → NO_TRADE
              </span>
              <span className="font-mono text-[11px] text-emerald-400">
                SOURCE_MODE: MARKET_ONLY
              </span>
            </div>
            <h3 className="mt-2 text-sm font-bold text-white">
              Official `@okx_ai/okx-trade-cli@1.4.8` Market Read (`site=tr`)
            </h3>
            <p className="mt-1 text-xs leading-relaxed text-slate-300">
              Executes real Node subprocess calls for <code className="font-mono">market ticker BTC-USDT</code> and{" "}
              <code className="font-mono">market instruments</code>, records SHA-256 stdout/result digests, evaluates LAYA/EVREN availability, and deterministically chooses <code className="font-mono">NO_TRADE (NOT_SENT)</code>.
            </p>
          </div>

          <div className="mt-4 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/80 pt-3">
            <span className="inline-flex items-center gap-1 font-mono text-[11px] text-slate-400">
              <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
              Proven in `http-smoke.json` & `latest.json`
            </span>
            <button
              type="button"
              onClick={() => onSelectPreset("real_atk_no_trade")}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-xs font-semibold transition ${
                activePreset === "real_atk_no_trade"
                  ? "bg-emerald-500 text-slate-950"
                  : "border border-emerald-500/40 bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25"
              }`}
            >
              {activePreset === "real_atk_no_trade"
                ? "Active View: Real ATK Market"
                : "Load Real ATK Market View"}
            </button>
          </div>
        </div>

        {/* Scenario 2: Synthetic Unsafe Duplicate / Unknown-Order / Stale State -> HALT */}
        <div
          className={`flex flex-col justify-between rounded-lg border p-4 transition ${
            activePreset !== "real_atk_no_trade"
              ? "border-amber-500/60 bg-amber-950/20 ring-1 ring-amber-500/40"
              : "border-slate-800 bg-slate-950/60 hover:border-slate-700"
          }`}
        >
          <div>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="inline-flex items-center gap-1.5 rounded bg-amber-500/20 px-2.5 py-0.5 font-mono text-xs font-bold text-amber-300 border border-amber-500/40">
                <FlaskConical className="h-3.5 w-3.5" />
                SCENARIO 2: SYNTHETIC UNSAFE STATE → HALT
              </span>
              <span className="rounded bg-amber-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-amber-300 border border-amber-500/40">
                MOCK SCENARIO
              </span>
            </div>
            <h3 className="mt-2 text-sm font-bold text-white">
              Deterministic Risk Gate Vetoes Unsafe Proposals (`NOT_SENT`)
            </h3>
            <p className="mt-1 text-xs leading-relaxed text-slate-300">
              Even when LAYA outputs <code className="font-mono">CONTINUE (1.0)</code> and a model proposes <code className="font-mono">BUY 0.0001 BTC</code>, the deterministic Python policy blocks execution on unknown prior orders, duplicate intents, stale feeds, or LAYA HALT.
            </p>

            {/* Sub-scenario buttons */}
            <div className="mt-3 grid grid-cols-2 gap-1.5 sm:grid-cols-4">
              {(
                [
                  {
                    key: "mock_unknown_order",
                    label: "Unknown Order",
                    rule: "unresolved_prior_order",
                    apiScenario: "unknown_order",
                  },
                  {
                    key: "mock_duplicate_intent",
                    label: "Duplicate Intent",
                    rule: "duplicate_intent",
                    apiScenario: "duplicate_intent",
                  },
                  {
                    key: "mock_stale_feed",
                    label: "Stale Feed",
                    rule: "stale_feed",
                    apiScenario: "stale_feed",
                  },
                  {
                    key: "mock_laya_halt",
                    label: "LAYA HALT",
                    rule: "laya_not_clear",
                    apiScenario: "laya_halt",
                  },
                ] as const
              ).map((item) => {
                const selected = activePreset === item.key;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => onSelectPreset(item.key)}
                    className={`flex flex-col items-start rounded border p-2 text-left transition ${
                      selected
                        ? "border-amber-400 bg-amber-500/25 text-white"
                        : "border-slate-800 bg-slate-900/90 text-slate-300 hover:border-slate-700"
                    }`}
                  >
                    <span className="text-xs font-bold">{item.label}</span>
                    <span className="mt-0.5 font-mono text-[10px] text-amber-300">
                      {item.rule}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/80 pt-3">
            <span className="inline-flex items-center gap-1 font-mono text-[11px] text-amber-300">
              <ShieldAlert className="h-3.5 w-3.5" />
              Clearly tagged MOCK — never claimed as real exchange demo
            </span>

            {adminUnlocked && backendSourceMode === "MOCK" && onTriggerLiveMockScenario && (
              <button
                type="button"
                disabled={busy}
                onClick={() => {
                  const map: Record<
                    DemoPresetKey,
                    "stale_feed" | "unknown_order" | "duplicate_intent" | "laya_halt"
                  > = {
                    real_atk_no_trade: "stale_feed",
                    mock_stale_feed: "stale_feed",
                    mock_unknown_order: "unknown_order",
                    mock_duplicate_intent: "duplicate_intent",
                    mock_laya_halt: "laya_halt",
                  };
                  onTriggerLiveMockScenario(map[activePreset]);
                }}
                className="inline-flex items-center gap-1 rounded border border-amber-500/40 bg-amber-500/20 px-2.5 py-1 text-xs font-semibold text-amber-200 hover:bg-amber-500/30 disabled:opacity-40"
              >
                <Play className="h-3 w-3" />
                Run on Backend (`/api/demo/scenario`)
              </button>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}
