"use client";

import React from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Activity,
  CheckCircle2,
  Cpu,
  FileCode2,
  Lock,
  Play,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Square,
  Wifi,
  WifiOff,
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

  return (
    <header className="sticky top-0 z-40 border-b border-slate-800/80 bg-slate-950/90 backdrop-blur-md">
      {/* Top Truthfulness & Safety Banner */}
      <div className="border-b border-slate-800/60 bg-slate-900/80 px-4 py-1.5 text-xs text-slate-300">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-2">
          <div className="flex flex-wrap items-center gap-2">
            <span className="inline-flex items-center gap-1 rounded bg-rose-500/15 px-2 py-0.5 font-mono text-[11px] font-semibold text-rose-300 border border-rose-500/30">
              LIVE_EXECUTION=DISABLED
            </span>
            <span className="inline-flex items-center gap-1 rounded bg-indigo-500/15 px-2 py-0.5 font-mono text-[11px] font-semibold text-indigo-300 border border-indigo-500/30">
              ORDER_PERMISSION=FALSE
            </span>
            <span className="text-slate-400">
              Off-chain Python/ATK runtime · On-chain Fuji ERC-8004 identity & SHA-256 receipts (no on-chain model inference)
            </span>
          </div>
          <div className="flex items-center gap-3 font-mono text-[11px]">
            {backendLive ? (
              <span className="inline-flex items-center gap-1 text-emerald-400">
                <CheckCircle2 className="h-3.5 w-3.5" />
                FASTAPI: LIVE HTTP
              </span>
            ) : (
              <span
                className="inline-flex items-center gap-1 rounded bg-amber-500/20 px-2 py-0.5 text-amber-300 border border-amber-500/40"
                title="FastAPI loopback server is currently stopped or unreachable; displaying real recorded evidence from backend/evidence/"
              >
                <ShieldAlert className="h-3.5 w-3.5" />
                BACKEND OFFLINE — RECORDED EVIDENCE MODE
              </span>
            )}
            <span
              className={`inline-flex items-center gap-1 ${
                sseState === "LIVE"
                  ? "text-emerald-400"
                  : sseState === "FALLBACK"
                  ? "text-amber-300"
                  : "text-slate-400"
              }`}
            >
              {sseState === "LIVE" ? (
                <Wifi className="h-3.5 w-3.5" />
              ) : (
                <WifiOff className="h-3.5 w-3.5" />
              )}
              SSE: {sseState}
            </span>
          </div>
        </div>
      </div>

      {/* Main Header Row */}
      <div className="mx-auto flex max-w-7xl flex-col gap-3 px-4 py-3 lg:flex-row lg:items-center lg:justify-between">
        <div className="flex flex-wrap items-center gap-3">
          <Link href="/" className="flex items-center gap-2.5 group">
            <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-emerald-500/10 border border-emerald-500/40 text-emerald-400 group-hover:bg-emerald-500/20 transition">
              <ShieldCheck className="h-6 w-6" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <span className="text-lg font-bold tracking-tight text-white">
                  AEGIS
                </span>
                <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wider text-slate-300 border border-slate-700">
                  v2.0 + Service v1
                </span>
              </div>
              <p className="text-xs text-slate-400">
                Autonomous Pre-Trade Risk & Self-Monitoring Service
              </p>
            </div>
          </Link>

          {/* Active Source Mode Badge */}
          <div
            className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 font-mono text-xs font-semibold ${modeInfo.badgeClass}`}
            title={modeInfo.description}
          >
            <Activity className="h-3.5 w-3.5" />
            <span>MODE: {modeInfo.badgeText}</span>
          </div>

          {/* Agent Loop Status */}
          <div
            className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 font-mono text-xs ${
              running
                ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300"
                : "border-slate-700 bg-slate-900 text-slate-300"
            }`}
          >
            <span
              className={`h-2 w-2 rounded-full ${
                running ? "animate-pulse bg-emerald-400" : "bg-slate-500"
              }`}
            />
            <span>LOOP: {running ? "RUNNING" : "STOPPED"}</span>
          </div>
        </div>

        {/* Timestamps + Navigation + Controls */}
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div className="hidden xl:flex flex-col text-right font-mono text-[11px] text-slate-400">
            <span>
              Market Observed:{" "}
              <strong className="text-slate-200">
                {observedAt ? observedAt.replace("T", " ").slice(0, 23) + "Z" : "N/A"}
              </strong>
            </span>
            <span>
              Last Cycle:{" "}
              <strong className="text-slate-200">
                {lastCycleAt ? lastCycleAt.replace("T", " ").slice(0, 23) + "Z" : "N/A"}
              </strong>
            </span>
          </div>

          {/* Navigation Tabs */}
          <nav
            aria-label="Primary Navigation"
            className="flex items-center rounded-lg border border-slate-800 bg-slate-900/90 p-1 text-xs font-medium"
          >
            <Link
              href="/"
              className={`rounded-md px-3 py-1.5 transition ${
                pathname === "/"
                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              1-Screen Control & Story
            </Link>
            <Link
              href="/service"
              className={`rounded-md px-3 py-1.5 transition ${
                pathname?.startsWith("/service")
                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              Use as Service (API)
            </Link>
            <Link
              href="/avalanche"
              className={`rounded-md px-3 py-1.5 transition ${
                pathname?.startsWith("/avalanche")
                  ? "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
                  : "text-slate-300 hover:text-white"
              }`}
            >
              Avalanche Fuji (43113)
            </Link>
          </nav>

          {/* Operator Controls (View-Only Judge Lock vs Admin) */}
          <div className="flex items-center gap-2">
            {onRefresh && (
              <button
                type="button"
                onClick={onRefresh}
                className="inline-flex items-center gap-1 rounded-md border border-slate-700 bg-slate-900 px-2.5 py-1.5 text-xs font-medium text-slate-200 hover:bg-slate-800 transition"
                title="Refresh snapshot and events from backend"
              >
                <RefreshCw className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Sync</span>
              </button>
            )}

            {adminUnlocked ? (
              <div className="flex items-center gap-1.5">
                <button
                  type="button"
                  disabled={controlBusy || running}
                  onClick={onStartAgent}
                  className="inline-flex items-center gap-1 rounded-md border border-emerald-500/40 bg-emerald-500/15 px-2.5 py-1.5 text-xs font-semibold text-emerald-300 hover:bg-emerald-500/25 disabled:opacity-40 transition"
                >
                  <Play className="h-3.5 w-3.5" />
                  Start
                </button>
                <button
                  type="button"
                  disabled={controlBusy || !running}
                  onClick={onStopAgent}
                  className="inline-flex items-center gap-1 rounded-md border border-rose-500/40 bg-rose-500/15 px-2.5 py-1.5 text-xs font-semibold text-rose-300 hover:bg-rose-500/25 disabled:opacity-40 transition"
                >
                  <Square className="h-3.5 w-3.5" />
                  Stop
                </button>
              </div>
            ) : (
              <button
                type="button"
                onClick={onOpenAdminModal}
                className="inline-flex items-center gap-1.5 rounded-md border border-slate-700 bg-slate-900/90 px-2.5 py-1.5 text-xs font-medium text-slate-300 hover:border-slate-600 hover:text-white transition"
                title="Public view-only judge mode has zero trade/control privileges. Click to unlock operator controls if you have the local admin secret."
              >
                <Lock className="h-3.5 w-3.5 text-amber-400" />
                <span>View-Only Judge Mode</span>
              </button>
            )}

            <button
              type="button"
              onClick={onInspectProof}
              className="inline-flex items-center gap-1.5 rounded-md border border-indigo-500/50 bg-indigo-500/20 px-3 py-1.5 text-xs font-semibold text-indigo-200 hover:bg-indigo-500/30 transition"
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
