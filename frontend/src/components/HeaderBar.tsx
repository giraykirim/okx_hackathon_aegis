"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  Clock,
  FileCode2,
  Home,
  Info,
  Link2,
  Lock,
  Play,
  RefreshCw,
  Server,
  ShieldCheck,
  Square,
} from "lucide-react";
import {
  deriveRuntimeStatusModel,
  getSourceModeExplanation,
} from "@/lib/view-helpers";
import type { SourceMode } from "@/lib/types";

interface HeaderBarProps {
  sourceMode: SourceMode;
  running: boolean;
  backendLive: boolean;
  sseState: "CONNECTING" | "LIVE" | "FALLBACK" | "DISCONNECTED";
  lastCycleAt: string | null;
  observedAt: string | null;
  activeScenario?: string;
  onInspectProof: () => void;
  onOpenAdminModal: () => void;
  adminUnlocked: boolean;
  executionEnabled?: boolean;
  onStartAgent?: () => void;
  onStopAgent?: () => void;
  controlBusy?: boolean;
  onRefresh?: () => void;
}

export function HeaderBar({
  sourceMode,
  running,
  backendLive,
  sseState,
  lastCycleAt,
  observedAt,
  activeScenario = "live_backend",
  onInspectProof,
  onOpenAdminModal,
  adminUnlocked,
  executionEnabled = false,
  onStartAgent,
  onStopAgent,
  controlBusy,
  onRefresh,
}: HeaderBarProps) {
  const pathname = usePathname();
  const [showFlagsPopover, setShowFlagsPopover] = React.useState(false);
  const modeInfo = getSourceModeExplanation(sourceMode);

  const runtimeStatus = deriveRuntimeStatusModel({
    backendReachable: backendLive,
    isOfflineFixture: !backendLive,
    activeScenario,
    sourceMode,
    sseStatus:
      sseState === "LIVE"
        ? "LIVE"
        : sseState === "CONNECTING"
        ? "CONNECTING"
        : "FALLBACK",
    lastTimestampIso: observedAt || lastCycleAt,
  });

  // Section 11: Single top-level navigation: AEGIS | Overview | Activity | Risk Service | On-chain
  const navItems = [
    {
      href: "/",
      label: "Overview",
      icon: <Home className="h-3.5 w-3.5" />,
      active: pathname === "/",
    },
    {
      href: "/activity",
      label: "Activity",
      icon: <Activity className="h-3.5 w-3.5" />,
      active: pathname?.startsWith("/activity"),
    },
    {
      href: "/service",
      label: "Risk Service",
      icon: <Server className="h-3.5 w-3.5" />,
      active: pathname?.startsWith("/service"),
    },
    {
      href: "/avalanche",
      label: "On-chain",
      icon: <Link2 className="h-3.5 w-3.5" />,
      active: pathname?.startsWith("/avalanche"),
    },
  ];

  const runtimeToneClasses =
    runtimeStatus.tone === "mint"
      ? "border-[#4EE1C2]/40 bg-[#4EE1C2]/10 text-[#4EE1C2]"
      : runtimeStatus.tone === "teal"
      ? "border-[#14B8A6]/40 bg-[#14B8A6]/10 text-[#14B8A6]"
      : runtimeStatus.tone === "amber"
      ? "border-[#F59E0B]/40 bg-[#F59E0B]/10 text-[#F59E0B]"
      : "border-[#EF4444]/40 bg-[#EF4444]/10 text-[#EF4444]";

  return (
    <header className="sticky top-0 z-40 border-b border-[#2A3542]/70 bg-[#0A0D10]/92 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        {/* Left: AEGIS Brand + Single Top-Level Navigation */}
        <div className="flex flex-wrap items-center justify-between gap-5">
          <Link href="/" className="flex items-center gap-3 group">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#4EE1C2]/30 bg-[#4EE1C2]/10 text-[#4EE1C2] transition group-hover:border-[#4EE1C2]/60 group-hover:bg-[#4EE1C2]/15">
              <svg
                width="16"
                height="16"
                viewBox="0 0 24 24"
                fill="none"
                aria-hidden="true"
              >
                <path
                  d="M12 3L3 20H8.5L12 13L15.5 20H21L12 3Z"
                  fill="currentColor"
                />
              </svg>
            </div>
            <span className="font-sans text-base font-bold tracking-[0.26em] text-[#E6EDF3]">
              AEGIS
            </span>
          </Link>

          <nav
            aria-label="Primary Navigation"
            className="flex items-center gap-1 rounded-xl border border-[#2A3542]/70 bg-[#11161D]/90 p-1 text-xs font-medium"
          >
            {navItems.map((item) => (
              <Link
                key={item.href}
                href={item.href}
                className={`relative inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 transition-all ${
                  item.active
                    ? "bg-[#1A222B] text-[#4EE1C2] shadow-[inset_0_1px_0_0_rgba(78,225,194,0.2)] border border-[#4EE1C2]/35"
                    : "text-[#9BA7B4] hover:bg-[#1A222B]/50 hover:text-[#E6EDF3]"
                }`}
              >
                {item.icon}
                <span>{item.label}</span>
              </Link>
            ))}
          </nav>
        </div>

        {/* Right: Compact Status Indicators + Operator Controls */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
            {/* 1. Explicit Runtime Connection State Badge (P0-1) */}
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-semibold ${runtimeToneClasses}`}
              title={`${runtimeStatus.subtitle} (${runtimeStatus.relativeAgeText})`}
            >
              <span
                className={`h-1.5 w-1.5 rounded-full bg-current ${
                  runtimeStatus.isLiveConnected ? "animate-pulse" : ""
                }`}
              />
              <span>{runtimeStatus.badgeLabel}</span>
            </span>

            {/* 2. Source Mode Chip */}
            <span
              className="inline-flex items-center gap-1.5 rounded-full border border-[#2A3542] bg-[#11161D] px-2.5 py-1 font-medium text-[#E6EDF3]"
              title={modeInfo.description}
            >
              <span>{sourceMode}</span>
            </span>

            {/* 3. Compact Safety Posture Summary with Protocol Flag Disclosure (P2-12) */}
            <div className="relative">
              <button
                type="button"
                onClick={() => setShowFlagsPopover((prev) => !prev)}
                className="inline-flex items-center gap-1.5 rounded-full border border-[#2A3542] bg-[#11161D] px-2.5 py-1 font-sans text-[11px] font-medium text-[#9BA7B4] hover:border-[#4EE1C2]/40 hover:text-[#E6EDF3] transition"
                title="LIVE_EXECUTION_DISABLED · ORDER_PERMISSION_FALSE — Click to inspect protocol flags"
              >
                <ShieldCheck className="h-3.5 w-3.5 text-[#4EE1C2]" />
                <span>
                  {executionEnabled && sourceMode === "OKX_DEMO"
                    ? "Demo trading armed · Policy gated"
                    : "Read-only · Trading disabled"}
                </span>
                <Info className="h-3 w-3 text-[#6E7785]" />
              </button>

              {showFlagsPopover && (
                <div className="absolute right-0 top-full z-50 mt-2 w-72 rounded-xl border border-[#2A3542] bg-[#11161D] p-3 shadow-2xl text-left font-sans">
                  <div className="flex items-center justify-between border-b border-[#2A3542]/70 pb-2">
                    <span className="text-xs font-semibold text-[#E6EDF3]">
                      Safety & Execution Posture
                    </span>
                    <button
                      type="button"
                      onClick={() => setShowFlagsPopover(false)}
                      className="text-[11px] text-[#9BA7B4] hover:text-[#E6EDF3]"
                    >
                      Close
                    </button>
                  </div>
                  <div className="mt-2.5 space-y-2 text-[11px]">
                    <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 px-2.5 py-1.5">
                      <div className="font-mono font-semibold text-[#EF4444]">
                        LIVE_EXECUTION_DISABLED
                      </div>
                      <p className="mt-0.5 text-[#9BA7B4]">
                        Real-money order submission is permanently disabled in
                        architecture.
                      </p>
                    </div>
                    <div className="rounded-lg border border-[#F59E0B]/30 bg-[#F59E0B]/10 px-2.5 py-1.5">
                      <div className="font-mono font-semibold text-[#F59E0B]">
                        ORDER_PERMISSION_FALSE
                      </div>
                      <p className="mt-0.5 text-[#9BA7B4]">
                        LAYA, EVREN, and external service calls never grant
                        exchange execution authority.
                      </p>
                    </div>
                    <div className="flex items-center gap-1.5 pt-1 font-mono text-[10px] text-[#6E7785]">
                      <Clock className="h-3 w-3" />
                      <span>{runtimeStatus.relativeAgeText}</span>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {/* 4. Avalanche Fuji 43113 Chip */}
            <Link
              href="/avalanche"
              className="hidden xl:inline-flex items-center gap-1.5 rounded-full border border-[#2A3542] bg-[#11161D] px-2.5 py-1 text-[#E6EDF3] hover:border-[#4EE1C2]/40 transition"
              title="Avalanche Fuji C-Chain (43113) ERC-8004 Identity & Audit Proof"
            >
              <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-[#EF4444] text-[8px] font-bold text-white">
                ▲
              </span>
              <span>Fuji 43113</span>
            </Link>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-1.5">
            {onRefresh && (
              <button
                type="button"
                onClick={onRefresh}
                className="inline-flex items-center gap-1 rounded-lg border border-[#2A3542] bg-[#11161D] px-2.5 py-1.5 text-xs font-medium text-[#9BA7B4] hover:border-[#4EE1C2]/40 hover:text-[#E6EDF3] transition"
                title={`${runtimeStatus.subtitle} · ${runtimeStatus.relativeAgeText}`}
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span className="hidden 2xl:inline">
                  {runtimeStatus.relativeAgeText}
                </span>
              </button>
            )}

            {adminUnlocked ? (
              <div className="flex items-center gap-1">
                <button
                  type="button"
                  disabled={controlBusy || running}
                  onClick={onStartAgent}
                  className="inline-flex items-center gap-1 rounded-lg border border-[#4EE1C2]/40 bg-[#4EE1C2]/15 px-2.5 py-1.5 text-xs font-semibold text-[#4EE1C2] hover:bg-[#4EE1C2]/25 disabled:opacity-40 transition"
                >
                  <Play className="h-3.5 w-3.5" />
                  Start
                </button>
                <button
                  type="button"
                  disabled={controlBusy || !running}
                  onClick={onStopAgent}
                  className="inline-flex items-center gap-1 rounded-lg border border-[#EF4444]/40 bg-[#EF4444]/15 px-2.5 py-1.5 text-xs font-semibold text-[#EF4444] hover:bg-[#EF4444]/25 disabled:opacity-40 transition"
                >
                  <Square className="h-3.5 w-3.5" />
                  Stop
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={onOpenAdminModal}
                className="inline-flex items-center gap-1.5 rounded-lg border border-[#2A3542] bg-[#11161D] px-2.5 py-1.5 text-xs font-medium text-[#9BA7B4] hover:border-[#4EE1C2]/40 hover:text-[#E6EDF3] transition"
                title="View-Only Judge Mode active. Click to enter local operator secret."
              >
                <Lock className="h-3.5 w-3.5 text-[#F59E0B]" />
                <span className="hidden md:inline">Judge Lock</span>
              </button>
            )}

            <button
              type="button"
              onClick={onInspectProof}
              className="inline-flex items-center gap-1.5 rounded-lg bg-[#4EE1C2] px-3 py-1.5 text-xs font-semibold text-[#0A0D10] hover:bg-[#4EE1C2]/90 transition"
            >
              <FileCode2 className="h-3.5 w-3.5" />
              <span>Inspect Proof</span>
            </button>
          </div>
        </div>
      </div>
    </header>
  );
}
