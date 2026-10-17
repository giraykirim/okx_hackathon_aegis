"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  FileCode2,
  Home,
  Link2,
  Lock,
  Play,
  RefreshCw,
  Server,
  Square,
} from "lucide-react";
import { getSourceModeExplanation } from "@/lib/view-helpers";
import type { SourceMode } from "@/lib/types";

interface HeaderBarProps {
  sourceMode: SourceMode;
  running: boolean;
  backendLive: boolean;
  sseState: "CONNECTING" | "LIVE" | "FALLBACK" | "DISCONNECTED";
  lastCycleAt: string | null;
  observedAt: string | null;
  onInspectProof: () => void;
  onOpenAdminModal: () => void;
  adminUnlocked: boolean;
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
  onInspectProof,
  onOpenAdminModal,
  adminUnlocked,
  onStartAgent,
  onStopAgent,
  controlBusy,
  onRefresh,
}: HeaderBarProps) {
  const pathname = usePathname();
  const modeInfo = getSourceModeExplanation(sourceMode);

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
      href: "/avalanche",
      label: "On-chain",
      icon: <Link2 className="h-3.5 w-3.5" />,
      active: pathname?.startsWith("/avalanche"),
    },
    {
      href: "/service",
      label: "Risk Service",
      icon: <Server className="h-3.5 w-3.5" />,
      active: pathname?.startsWith("/service"),
    },
  ];

  return (
    <header className="sticky top-0 z-40 border-b border-[#2A3542]/70 bg-[#0A0D10]/90 backdrop-blur-xl">
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        {/* Left: AEGIS Brand + Primary Navigation */}
        <div className="flex flex-wrap items-center justify-between gap-5">
          <Link href="/" className="flex items-center gap-3 group">
            {/* Geometric Aegis Triangle Mark (Reference Set A/B/C/D) */}
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

          {/* Navigation Tabs */}
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

        {/* Right: Global Status Chips + Operator Controls (Reference Set A) */}
        <div className="flex flex-wrap items-center justify-between gap-2">
          {/* Status Chips */}
          <div className="flex flex-wrap items-center gap-1.5 font-mono text-[11px]">
            {/* 1. Source Mode Chip */}
            <span
              className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-semibold ${
                sourceMode === "MOCK"
                  ? "border-[#F59E0B]/40 bg-[#F59E0B]/10 text-[#F59E0B]"
                  : "border-[#4EE1C2]/35 bg-[#4EE1C2]/10 text-[#4EE1C2]"
              }`}
              title={modeInfo.description}
            >
              <span className="h-1.5 w-1.5 rounded-full bg-current" />
              {sourceMode}
            </span>

            {/* 2. LIVE_EXECUTION_DISABLED Chip */}
            <span
              className="inline-flex items-center gap-1.5 rounded-full border border-[#EF4444]/35 bg-[#EF4444]/10 px-2.5 py-1 font-semibold text-[#EF4444]"
              title="Live real-money trading is permanently disabled by architecture"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-[#EF4444]" />
              LIVE_EXECUTION_DISABLED
            </span>

            {/* 3. ORDER_PERMISSION_FALSE Chip */}
            <span
              className="inline-flex items-center gap-1.5 rounded-full border border-[#F59E0B]/35 bg-[#F59E0B]/10 px-2.5 py-1 font-semibold text-[#F59E0B]"
              title="Advisory models and service responses never grant order execution permission"
            >
              <span className="h-1.5 w-1.5 rounded-full bg-[#F59E0B]" />
              ORDER_PERMISSION_FALSE
            </span>

            {/* 4. Avalanche Fuji 43113 Chip */}
            <Link
              href="/avalanche"
              className="hidden sm:inline-flex items-center gap-1.5 rounded-full border border-[#2A3542] bg-[#11161D] px-2.5 py-1 text-[#E6EDF3] hover:border-[#4EE1C2]/40 transition"
              title="Avalanche Fuji C-Chain (43113) ERC-8004 Identity & Receipt Verifier"
            >
              <span className="flex h-3.5 w-3.5 items-center justify-center rounded-full bg-[#EF4444] text-[8px] font-bold text-white">
                ▲
              </span>
              <span>Avalanche Fuji 43113</span>
            </Link>
          </div>

          {/* Action Buttons */}
          <div className="flex items-center gap-1.5">
            {onRefresh && (
              <button
                type="button"
                onClick={onRefresh}
                className="inline-flex items-center gap-1 rounded-lg border border-[#2A3542] bg-[#11161D] px-2.5 py-1.5 text-xs font-medium text-[#9BA7B4] hover:border-[#4EE1C2]/40 hover:text-[#E6EDF3] transition"
                title={`Sync state (SSE: ${sseState}, Last Cycle: ${lastCycleAt ?? "N/A"}, Market: ${observedAt ?? "N/A"})`}
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span className="hidden xl:inline">
                  {backendLive ? "Live Sync" : "Recorded Proof"}
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
