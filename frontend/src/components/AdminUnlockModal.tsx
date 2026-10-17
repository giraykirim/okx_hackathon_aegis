"use client";

import React from "react";
import { KeyRound, Lock, ShieldAlert, Unlock, X } from "lucide-react";

interface AdminUnlockModalProps {
  open: boolean;
  onClose: () => void;
  adminSecret: string;
  onSaveSecret: (secret: string) => void;
  statusMessage?: string | null;
}

export function AdminUnlockModal({
  open,
  onClose,
  adminSecret,
  onSaveSecret,
  statusMessage,
}: AdminUnlockModalProps) {
  const [draft, setDraft] = React.useState(adminSecret);

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Operator Control Authentication"
      className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 p-4 backdrop-blur-sm"
    >
      <div className="w-full max-w-md rounded-xl border border-slate-700 bg-slate-900 p-5 shadow-2xl">
        <div className="flex items-center justify-between border-b border-slate-800 pb-3">
          <div className="flex items-center gap-2">
            <Lock className="h-4 w-4 text-amber-400" />
            <h2 className="text-sm font-bold text-white">
              Operator Admin Controls (Judge View-Only Protection)
            </h2>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-slate-700 bg-slate-800 p-1 text-slate-300 hover:text-white"
            aria-label="Close Admin Modal"
          >
            <X className="h-4 w-4" />
          </button>
        </div>

        <div className="mt-3 space-y-3 text-xs text-slate-300">
          <div className="rounded-lg border border-amber-500/30 bg-amber-950/20 p-3 text-amber-200">
            <div className="flex items-center gap-1.5 font-semibold">
              <ShieldAlert className="h-4 w-4 shrink-0 text-amber-400" />
              Why is this locked by default?
            </div>
            <p className="mt-1 text-[11px] leading-relaxed text-amber-100/90">
              Public judge access is strictly <strong>view-only with zero trade privileges</strong>. Backend control tokens (<code className="font-mono">AEGIS_CONTROL_TOKEN</code>) are kept in private Next.js server memory and are never exposed in <code className="font-mono">NEXT_PUBLIC_*</code> or client bundles.
            </p>
          </div>

          <div>
            <label
              htmlFor="admin-secret-input"
              className="block font-mono text-[11px] font-semibold text-slate-300"
            >
              Local Operator Secret (`X-AEGIS-Admin-Secret` in memory only):
            </label>
            <div className="mt-1.5 flex items-center gap-2">
              <KeyRound className="h-4 w-4 text-slate-500" />
              <input
                id="admin-secret-input"
                type="password"
                value={draft}
                onChange={(e) => setDraft(e.target.value)}
                placeholder="Enter local AEGIS_DASHBOARD_ADMIN_SECRET..."
                className="w-full rounded-md border border-slate-700 bg-slate-950 px-3 py-1.5 font-mono text-xs text-white placeholder-slate-500 focus:border-indigo-500 focus:outline-none"
              />
            </div>
            <p className="mt-1 text-[10px] text-slate-400">
              Stored only in volatile React component state (never in <code className="font-mono">localStorage</code> or cookies).
            </p>
          </div>

          {statusMessage && (
            <div className="rounded border border-rose-500/40 bg-rose-950/30 p-2 font-mono text-[11px] text-rose-300">
              {statusMessage}
            </div>
          )}
        </div>

        <div className="mt-4 flex items-center justify-end gap-2 border-t border-slate-800 pt-3">
          {adminSecret && (
            <button
              type="button"
              onClick={() => {
                onSaveSecret("");
                onClose();
              }}
              className="rounded-md border border-slate-700 bg-slate-800 px-3 py-1.5 text-xs font-medium text-slate-300 hover:text-white"
            >
              Lock View-Only Mode
            </button>
          )}
          <button
            type="button"
            onClick={() => {
              onSaveSecret(draft.trim());
              onClose();
            }}
            className="inline-flex items-center gap-1.5 rounded-md bg-emerald-500 px-3.5 py-1.5 text-xs font-bold text-slate-950 hover:bg-emerald-400"
          >
            <Unlock className="h-3.5 w-3.5" />
            {draft.trim() ? "Enable Operator Session" : "Stay View-Only"}
          </button>
        </div>
      </div>
    </div>
  );
}
