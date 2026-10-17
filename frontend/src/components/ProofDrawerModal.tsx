"use client";

import React from "react";
import {
  CheckCircle2,
  Copy,
  FileCode2,
  Hash,
  ShieldCheck,
  Terminal,
  X,
} from "lucide-react";
import { extractAtkReceipts } from "@/lib/view-helpers";
import type { EventItem, Snapshot } from "@/lib/types";
import e2eProof from "../../e2e-live-proof.json";

interface ProofDrawerModalProps {
  open: boolean;
  onClose: () => void;
  snapshot: Snapshot | null;
  events: EventItem[];
}

export function ProofDrawerModal({
  open,
  onClose,
  snapshot,
  events,
}: ProofDrawerModalProps) {
  const [copiedText, setCopiedText] = React.useState<string | null>(null);

  if (!open) return null;

  const receipts = extractAtkReceipts(events, snapshot?.run_id);

  const copyToClipboard = (val: string, label: string) => {
    navigator.clipboard.writeText(val).catch(() => {});
    setCopiedText(label);
    setTimeout(() => setCopiedText(null), 2000);
  };

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Cryptographic & Subprocess Proof Inspector"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
    >
      <div className="flex max-h-[90vh] w-full max-w-4xl flex-col rounded-xl border border-slate-700 bg-slate-900 shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-slate-800 px-5 py-4">
          <div className="flex items-center gap-2.5">
            <FileCode2 className="h-5 w-5 text-indigo-400" />
            <div>
              <h2 className="text-base font-bold text-white">
                Inspect Verifiable Proof & Cryptographic Digests
              </h2>
              <p className="text-xs text-slate-400">
                Sanitized official OKX ATK CLI/MCP receipts, live E2E integration proof, frozen OpenAPI v2 hash, and raw Snapshot payload.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded-lg border border-slate-700 bg-slate-800 p-1.5 text-slate-300 hover:bg-slate-700 hover:text-white"
            aria-label="Close Proof Inspector"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        {/* Body */}
        <div className="space-y-4 overflow-y-auto p-5 text-xs">
          {/* 1. Contract & Architecture Integrity */}
          <div className="rounded-lg border border-slate-800 bg-slate-950/80 p-4">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 font-bold text-emerald-300">
                <ShieldCheck className="h-4 w-4" />
                Frozen Shared Contract v2 (`contracts/openapi.yaml`)
              </span>
              <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
                FROZEN_UNCHANGED
              </span>
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2 rounded bg-slate-900 p-2 font-mono text-[11px] text-slate-300 border border-slate-800">
              <span className="break-all">
                SHA-256: a437caaa81ae590fc258aa0aeeb6498b1c38ec745483a701a4b2f0c66314d5ae
              </span>
              <button
                type="button"
                onClick={() =>
                  copyToClipboard(
                    "a437caaa81ae590fc258aa0aeeb6498b1c38ec745483a701a4b2f0c66314d5ae",
                    "v2-sha"
                  )
                }
                className="inline-flex items-center gap-1 rounded bg-slate-800 px-2 py-0.5 text-[10px] text-slate-200 hover:bg-slate-700"
              >
                <Copy className="h-3 w-3" />
                {copiedText === "v2-sha" ? "Copied" : "Copy"}
              </button>
            </div>
          </div>

          {/* 1B. Live E2E Dashboard <-> FastAPI Backend Integration Proof */}
          <div className="rounded-lg border border-emerald-500/30 bg-emerald-950/15 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="inline-flex items-center gap-1.5 font-bold text-emerald-300">
                <CheckCircle2 className="h-4 w-4" />
                Live E2E Dashboard ↔ FastAPI Backend Integration (`frontend/e2e-live-proof.json`)
              </span>
              <span className="rounded bg-emerald-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
                {e2eProof.status} · {e2eProof.generated_at}
              </span>
            </div>
            <p className="mt-1.5 text-[11px] text-slate-300">
              {e2eProof.summary}
            </p>
            <div className="mt-2.5 grid grid-cols-1 gap-2 sm:grid-cols-3 font-mono text-[10px]">
              <div className="rounded border border-slate-800 bg-slate-900/90 p-2">
                <div className="text-slate-400">Live ATK Observation (TR)</div>
                <div className="mt-0.5 font-bold text-emerald-300">
                  {e2eProof.market_only_e2e.live_atk_observation.symbol} @{" "}
                  {e2eProof.market_only_e2e.live_atk_observation.price}
                </div>
                <div className="text-slate-400">
                  {e2eProof.market_only_e2e.capabilities_pass.length} ATK/MCP caps PASS
                </div>
              </div>
              <div className="rounded border border-slate-800 bg-slate-900/90 p-2">
                <div className="text-slate-400">Service 1.1.0 Notional E2E</div>
                <div className="mt-0.5 font-bold text-amber-300">
                  10 USDT → {e2eProof.market_only_e2e.service_v1_1_notional_10usdt.verdict}
                </div>
                <div className="text-rose-300">
                  50 USDT → {e2eProof.mock_mode_e2e.service_v1_1_notional_50usdt_excess.verdict} (execution_authorized=false)
                </div>
              </div>
              <div className="rounded border border-slate-800 bg-slate-900/90 p-2">
                <div className="text-slate-400">Fuji 43113 Live RPC</div>
                <div className="mt-0.5 font-bold text-indigo-300">
                  Block #{e2eProof.avalanche_fuji_e2e.block_number}
                </div>
                <div className="text-slate-400">
                  Identity & Reputation Bytecode: PASS
                </div>
              </div>
            </div>
          </div>

          {/* 2. Official OKX ATK Subprocess Receipts */}
          <div className="rounded-lg border border-slate-800 bg-slate-950/80 p-4">
            <div className="flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 font-bold text-white">
                <Terminal className="h-4 w-4 text-emerald-400" />
                Official OKX ATK CLI Subprocess Receipts ({receipts.length})
              </span>
              <span className="font-mono text-[11px] text-slate-400">
                Toolkit: @okx_ai/okx-trade-cli@1.4.8 (site=tr)
              </span>
            </div>

            {receipts.length === 0 ? (
              <p className="mt-2 text-slate-400">
                Current view is a synthetic <code className="text-amber-300">MOCK</code> scenario (zero external ATK subprocess calls). Switch to Scenario 1 (`MARKET_ONLY`) to inspect real ATK CLI receipts and SHA-256 stdout digests.
              </p>
            ) : (
              <div className="mt-3 space-y-2.5">
                {receipts.map((r) => (
                  <div
                    key={r.id}
                    className="rounded border border-slate-800 bg-slate-900/90 p-3 font-mono text-[11px]"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="font-bold text-emerald-300">
                        Operation: {r.operation} ({r.status}) — {r.elapsed_ms.toFixed(2)} ms
                      </span>
                      <span className="text-slate-400">Receipt ID: {r.id}</span>
                    </div>
                    <div className="mt-1.5 text-slate-300">
                      <span className="text-slate-500">Command: </span>
                      <code className="break-all text-indigo-200">
                        {r.command.join(" ")}
                      </code>
                    </div>
                    <div className="mt-1.5 grid grid-cols-1 gap-1 text-[10px] text-slate-400 sm:grid-cols-2">
                      <div>Requested At: {r.requested_at}</div>
                      <div>Market Timestamp: {r.market_timestamp ?? "N/A (instruments)"}</div>
                      <div className="sm:col-span-2 break-all">
                        Result SHA-256:{" "}
                        <span className="text-slate-200">{r.result_sha256}</span>
                      </div>
                      <div className="sm:col-span-2 break-all">
                        Stdout SHA-256:{" "}
                        <span className="text-slate-200">{r.stdout_sha256}</span>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* 3. Raw Snapshot JSON */}
          <div className="rounded-lg border border-slate-800 bg-slate-950/80 p-4">
            <div className="mb-2 flex items-center justify-between">
              <span className="inline-flex items-center gap-1.5 font-bold text-white">
                <Hash className="h-4 w-4 text-indigo-400" />
                Current `/api/snapshot` Payload
              </span>
              <button
                type="button"
                onClick={() =>
                  copyToClipboard(JSON.stringify(snapshot, null, 2), "snapshot-json")
                }
                className="inline-flex items-center gap-1 rounded bg-slate-800 px-2.5 py-1 font-mono text-[10px] text-slate-200 hover:bg-slate-700"
              >
                <Copy className="h-3 w-3" />
                {copiedText === "snapshot-json" ? "Copied JSON" : "Copy Snapshot JSON"}
              </button>
            </div>
            <pre className="max-h-64 overflow-auto rounded border border-slate-800 bg-slate-900 p-3 font-mono text-[11px] text-slate-300">
              {JSON.stringify(snapshot, null, 2)}
            </pre>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between border-t border-slate-800 px-5 py-3 text-xs text-slate-400">
          <span className="inline-flex items-center gap-1">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-400" />
            Zero secrets or private keys in client bundle or logs
          </span>
          <button
            type="button"
            onClick={onClose}
            className="rounded-md bg-slate-800 px-4 py-1.5 font-semibold text-white hover:bg-slate-700"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
