"use client";

import React from "react";
import { FlaskConical, Play, Radio } from "lucide-react";

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
  const mockSubScenarios = [
    {
      key: "mock_unknown_order" as const,
      label: "Unknown Order",
      rule: "unresolved_prior_order",
    },
    {
      key: "mock_duplicate_intent" as const,
      label: "Duplicate Intent",
      rule: "duplicate_intent",
    },
    {
      key: "mock_stale_feed" as const,
      label: "Stale Feed",
      rule: "stale_feed",
    },
    {
      key: "mock_laya_halt" as const,
      label: "LAYA HALT",
      rule: "laya_not_clear",
    },
  ];

  const isMockActive = activePreset !== "real_atk_no_trade";

  return (
    <section
      aria-label="Jury Evaluation Scenarios"
      className="aegis-card flex flex-wrap items-center justify-between gap-3 rounded-xl px-4 py-3"
    >
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-[#9BA7B4] mr-1">
          SCENARIO PRESET
        </span>

        {/* Scenario 1: Real ATK Market */}
        <button
          type="button"
          onClick={() => onSelectPreset("real_atk_no_trade")}
          className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition ${
            activePreset === "real_atk_no_trade"
              ? "border-[#4EE1C2]/50 bg-[#4EE1C2]/15 text-[#4EE1C2] shadow-[inset_0_1px_0_0_rgba(78,225,194,0.25)]"
              : "border-[#2A3542] bg-[#0A0D10]/70 text-[#9BA7B4] hover:border-[#4EE1C2]/30 hover:text-[#E6EDF3]"
          }`}
        >
          <Radio className="h-3.5 w-3.5" />
          <span>1. Real OKX ATK Market (`MARKET_ONLY` → `NO_TRADE`)</span>
        </button>

        {/* Scenario 2: Synthetic Unsafe Veto Presets */}
        <div className="flex flex-wrap items-center gap-1 rounded-lg border border-[#2A3542] bg-[#0A0D10]/70 p-1">
          <span className="inline-flex items-center gap-1 px-2 font-mono text-[10px] font-semibold text-[#F59E0B]">
            <FlaskConical className="h-3 w-3" />
            2. MOCK VETO:
          </span>
          {mockSubScenarios.map((item) => {
            const selected = activePreset === item.key;
            return (
              <button
                key={item.key}
                type="button"
                onClick={() => onSelectPreset(item.key)}
                className={`rounded-md px-2.5 py-1 text-xs font-medium transition ${
                  selected
                    ? "bg-[#F59E0B]/20 text-[#F59E0B] border border-[#F59E0B]/40"
                    : "text-[#9BA7B4] hover:bg-[#1A222B] hover:text-[#E6EDF3]"
                }`}
                title={`Rule: ${item.rule} (execution_status=NOT_SENT)`}
              >
                {item.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex items-center gap-2 font-mono text-[11px]">
        {isMockActive ? (
          <span className="rounded-full border border-[#F59E0B]/35 bg-[#F59E0B]/10 px-2.5 py-0.5 text-[#F59E0B]">
            MOCK SCENARIO · Zero Exchange Calls
          </span>
        ) : (
          <span className="rounded-full border border-[#4EE1C2]/35 bg-[#4EE1C2]/10 px-2.5 py-0.5 text-[#4EE1C2]">
            @okx_ai/okx-trade-cli@1.4.8 (site=tr)
          </span>
        )}

        {adminUnlocked &&
          backendSourceMode === "MOCK" &&
          onTriggerLiveMockScenario && (
            <button
              type="button"
              disabled={busy}
              onClick={() => {
                const map: Record<
                  DemoPresetKey,
                  | "stale_feed"
                  | "unknown_order"
                  | "duplicate_intent"
                  | "laya_halt"
                > = {
                  real_atk_no_trade: "stale_feed",
                  mock_stale_feed: "stale_feed",
                  mock_unknown_order: "unknown_order",
                  mock_duplicate_intent: "duplicate_intent",
                  mock_laya_halt: "laya_halt",
                };
                onTriggerLiveMockScenario(map[activePreset]);
              }}
              className="inline-flex items-center gap-1 rounded-lg border border-[#F59E0B]/40 bg-[#F59E0B]/15 px-2.5 py-1 text-xs font-semibold text-[#F59E0B] hover:bg-[#F59E0B]/25 disabled:opacity-40"
            >
              <Play className="h-3 w-3" />
              Run Live Mock
            </button>
          )}
      </div>
    </section>
  );
}
