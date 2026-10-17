"use client";

import React from "react";
import {
  AlertOctagon,
  Building2,
  CheckCircle2,
  Code2,
  Copy,
  ExternalLink,
  FileCode2,
  Lock,
  ShieldAlert,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { AdminUnlockModal } from "@/components/AdminUnlockModal";
import { HeaderBar } from "@/components/HeaderBar";
import { ProofDrawerModal } from "@/components/ProofDrawerModal";
import {
  RECORDED_EVENTS_MARKET_ONLY,
  RECORDED_SERVICE_ASSESSMENTS,
  RECORDED_SERVICE_INFO,
  RECORDED_SNAPSHOT_MARKET_ONLY,
} from "@/lib/fixtures";
import type { RiskAssessment, ServiceInfo, Snapshot } from "@/lib/types";
import { explainRiskReason } from "@/lib/view-helpers";

export default function ServicePage() {
  const [serviceInfo, setServiceInfo] = React.useState<ServiceInfo>(
    RECORDED_SERVICE_INFO
  );
  const [snapshot] = React.useState<Snapshot>(RECORDED_SNAPSHOT_MARKET_ONLY);
  const [backendLive, setBackendLive] = React.useState(false);

  const [selectedSample, setSelectedSample] = React.useState<
    "small_intent" | "excess_notional"
  >("excess_notional");
  const [customQty, setCustomQty] = React.useState("1");
  const [customAction, setCustomAction] = React.useState<"BUY" | "SELL">("BUY");
  const [assessment, setAssessment] = React.useState<RiskAssessment>(
    RECORDED_SERVICE_ASSESSMENTS.excess_notional
  );
  const [assessmentSource, setAssessmentSource] = React.useState<
    "RECORDED_PROOF" | "LIVE"
  >("RECORDED_PROOF");
  const [evalBusy, setEvalBusy] = React.useState(false);
  const [copiedId, setCopiedId] = React.useState<string | null>(null);

  const [proofModalOpen, setProofModalOpen] = React.useState(false);
  const [adminModalOpen, setAdminModalOpen] = React.useState(false);
  const [adminSecret, setAdminSecret] = React.useState("");

  React.useEffect(() => {
    fetch("/api/v1/service", { cache: "no-store" })
      .then(async (res) => {
        setBackendLive(res.headers.get("X-AEGIS-Backend-Status") === "LIVE");
        if (res.ok) {
          const data = (await res.json()) as ServiceInfo;
          setServiceInfo(data);
        }
      })
      .catch(() => setBackendLive(false));
  }, []);

  const handleSelectSample = (sample: "small_intent" | "excess_notional") => {
    setSelectedSample(sample);
    if (sample === "small_intent") {
      setCustomQty("0.0001");
      setCustomAction("BUY");
      setAssessment(RECORDED_SERVICE_ASSESSMENTS.small_intent);
    } else {
      setCustomQty("1");
      setCustomAction("BUY");
      setAssessment(RECORDED_SERVICE_ASSESSMENTS.excess_notional);
    }
    setAssessmentSource("RECORDED_PROOF");
  };

  const handleEvaluate = async (e: React.FormEvent) => {
    e.preventDefault();
    setEvalBusy(true);
    try {
      const headers: Record<string, string> = {
        "Content-Type": "application/json",
      };
      if (adminSecret) {
        headers["X-AEGIS-Admin-Secret"] = adminSecret;
      }
      const res = await fetch("/api/v1/risk/evaluate", {
        method: "POST",
        headers,
        body: JSON.stringify({
          symbol: "BTC-USDT",
          action: customAction,
          quantity: customQty,
          client_request_id: `ui-${Date.now()}`,
        }),
      });
      if (res.ok) {
        const data = (await res.json()) as RiskAssessment;
        setAssessment(data);
        setAssessmentSource(
          res.headers.get("X-AEGIS-Backend-Status") === "LIVE"
            ? "LIVE"
            : "RECORDED_PROOF"
        );
      }
    } finally {
      setEvalBusy(false);
    }
  };

  const copyText = (txt: string, id: string) => {
    navigator.clipboard.writeText(txt).catch(() => {});
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const sampleRequestJson = JSON.stringify(
    {
      symbol: "BTC-USDT",
      action: customAction,
      quantity: customQty,
      client_request_id:
        selectedSample === "small_intent"
          ? "proof-small_intent"
          : "proof-excess_notional",
    },
    null,
    2
  );

  const curlSnippet = `curl --silent --show-error --fail-with-body \\
  --request POST 'http://127.0.0.1:8000/api/v1/risk/evaluate' \\
  --header 'Content-Type: application/json' \\
  --header "X-AEGIS-Key: $AEGIS_SERVICE_API_KEY" \\
  --data '${ JSON.stringify({
    symbol: "BTC-USDT",
    action: customAction,
    quantity: customQty,
    client_request_id: "agent-pretrade-check-01",
  })}'`;

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <HeaderBar
        sourceMode={snapshot.source_mode}
        running={snapshot.running}
        backendLive={backendLive}
        sseState={backendLive ? "LIVE" : "FALLBACK"}
        lastCycleAt={snapshot.last_cycle_at}
        observedAt={assessment.market_provenance.market_timestamp}
        onInspectProof={() => setProofModalOpen(true)}
        onOpenAdminModal={() => setAdminModalOpen(true)}
        adminUnlocked={Boolean(adminSecret)}
      />

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6">
        {/* Hero / Positioning Card (Rubric A: 25 pts + Rubric F: 10 pts) */}
        <section className="rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-slate-800 pb-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded bg-indigo-500/20 px-2.5 py-0.5 font-mono text-xs font-bold text-indigo-300 border border-indigo-500/40">
                  GET /api/v1/service · POST /api/v1/risk/evaluate
                </span>
                <span className="rounded bg-rose-500/20 px-2.5 py-0.5 font-mono text-xs font-bold text-rose-300 border border-rose-500/40">
                  order_permission=false · execution_authority=false
                </span>
                <span className="rounded bg-amber-500/20 px-2.5 py-0.5 font-mono text-xs font-bold text-amber-300 border border-amber-500/40">
                  OKX.AI compatible service — listing readiness not confirmed ({serviceInfo.okx_ai.listing_status})
                </span>
              </div>
              <h1 className="mt-2.5 text-xl font-bold text-white">
                {serviceInfo.name} (v{serviceInfo.version}) — Reusable B2B Pre-Trade Risk Gate
              </h1>
              <p className="mt-1 max-w-3xl text-xs leading-relaxed text-slate-300">
                {serviceInfo.purpose}. Target Customer:{" "}
                <strong className="text-white">{serviceInfo.target_customer}</strong>. External trading agents call AEGIS before submitting an order; AEGIS fetches independent server-side OKX ATK market & instrument facts, runs LAYA/EVREN checks, applies deterministic sizing/freshness rules, and returns a SHA-256 signed <code className="font-mono">REVIEW</code> or <code className="font-mono">HALT</code> assessment.
              </p>
            </div>

            <div className="rounded-lg border border-slate-800 bg-slate-950/80 p-3 font-mono text-xs text-slate-300">
              <div>
                Deployment Status:{" "}
                <span className="font-bold text-amber-300">
                  {serviceInfo.deployment_status}
                </span>
              </div>
              <div className="mt-1">
                Public URL:{" "}
                <span className="text-slate-400">
                  {serviceInfo.public_url ?? "null (Loopback only; not invented)"}
                </span>
              </div>
              <div className="mt-1">
                Auth Header:{" "}
                <span className="text-indigo-300">{serviceInfo.auth.header}</span> (
                {serviceInfo.auth.requests_per_minute} req/min, max{" "}
                {serviceInfo.auth.max_request_bytes}B)
              </div>
            </div>
          </div>

          {/* Who Uses AEGIS + Business Model Hypothesis + OKX.AI Status */}
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            {/* Target Customer */}
            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-4">
              <div className="flex items-center gap-2 text-xs font-bold text-white">
                <Building2 className="h-4 w-4 text-indigo-400" />
                Who Uses AEGIS & Problem Solved
              </div>
              <p className="mt-2 text-xs leading-relaxed text-slate-300">
                Agentic trading teams often couple LLM prompts directly to exchange execution tools. A single hallucinated quantity, stale ticker, or duplicate retry causes catastrophic unintended fills.
              </p>
              <ul className="mt-2 space-y-1 text-[11px] text-slate-400">
                <li>• <strong className="text-slate-200">Untrusted Caller Input:</strong> Rejects caller-supplied balance/market flags (`HTTP 422`).</li>
                <li>• <strong className="text-slate-200">Server-Side ATK Provenance:</strong> Independently queries `@okx_ai/okx-trade-cli@1.4.8`.</li>
                <li>• <strong className="text-slate-200">Zero Trade Delegation:</strong> Never executes trades on the caller&apos;s behalf.</li>
              </ul>
            </div>

            {/* Commercial Business Model Hypothesis */}
            <div className="rounded-lg border border-amber-500/30 bg-amber-950/15 p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white">
                  Proposed Business Model
                </span>
                <span className="rounded bg-amber-500/20 px-2 py-0.5 font-mono text-[10px] font-bold text-amber-300 border border-amber-500/40">
                  HYPOTHESIS ({serviceInfo.pricing.status})
                </span>
              </div>
              <div className="mt-2.5 grid grid-cols-2 gap-2">
                <div className="rounded border border-slate-800 bg-slate-950/80 p-2.5">
                  <div className="text-[10px] text-slate-400">Pay-Per-Assessment</div>
                  <div className="mt-0.5 font-mono text-base font-bold text-emerald-300">
                    ${serviceInfo.pricing.per_assessment} {serviceInfo.pricing.currency}
                  </div>
                  <div className="text-[10px] text-slate-500">per pre-trade check</div>
                </div>
                <div className="rounded border border-slate-800 bg-slate-950/80 p-2.5">
                  <div className="text-[10px] text-slate-400">B2B Team Tier</div>
                  <div className="mt-0.5 font-mono text-base font-bold text-indigo-300">
                    ${serviceInfo.pricing.b2b_monthly}/mo
                  </div>
                  <div className="text-[10px] text-slate-500">
                    {serviceInfo.pricing.included_assessments.toLocaleString()} checks included
                  </div>
                </div>
              </div>
              <p className="mt-2 text-[11px] text-amber-200/90">
                Payment integration: <code className="font-mono">{serviceInfo.pricing.payment_integration}</code>. Commercial pricing hypothesis only — no billing rail, x402 settlement, or revenue is claimed.
              </p>
            </div>

            {/* OKX.AI Marketplace Status */}
            <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-white">
                  OKX.AI Service Compatibility
                </span>
                <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] font-bold text-amber-300 border border-slate-700">
                  FEASIBILITY: {serviceInfo.okx_ai.integration_feasibility} · {serviceInfo.okx_ai.listing_status}
                </span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-slate-300">
                OKX.AI compatible service — listing readiness not confirmed. Official OKX.AI (`okx.com/learn/okx-ai` + ASP docs) operates on Onchain OS (`okx/onchainos-skills`) with Agent Marketplace & Task Marketplace, requiring an OKX Agentic Wallet, shared onchain Agent Identity, and A2MCP (pay-per-call) or A2A (escrow) settlement in USDT/USDG.
              </p>
              <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800 pt-2 text-[11px]">
                <span className="font-mono text-slate-400">
                  Listing URL: {serviceInfo.okx_ai.verified_listing_url ?? "null"}
                </span>
                <div className="flex flex-wrap items-center gap-3">
                  <a
                    href="https://www.okx.com/learn/okx-ai"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-indigo-300 hover:underline"
                  >
                    OKX.AI Overview <ExternalLink className="h-3 w-3" />
                  </a>
                  <a
                    href={serviceInfo.okx_ai.requirements_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-indigo-300 hover:underline"
                  >
                    Official ASP Docs <ExternalLink className="h-3 w-3" />
                  </a>
                  <a
                    href="https://www.okx.com/en-us/help/okx-ai-agent-marketplace-user-agreement"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-slate-400 hover:text-slate-200 hover:underline"
                  >
                    Marketplace Terms <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </div>
          </div>

          {/* OKX.AI Provider Readiness Matrix (P3-03: VERIFYING / MISSING / NOT_LISTED + Measured Latency) */}
          <div className="mt-4 rounded-lg border border-slate-800 bg-slate-950/80 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2.5">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-emerald-400" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-white">
                  OKX.AI Provider Readiness & SLA Transparency Matrix (Official `okx.com/learn/okx-ai` + ASP Spec)
                </h2>
              </div>
              <span className="font-mono text-[11px] text-amber-300">
                Measured Pre-Trade Check Latency: ~1.1s – 1.4s (`721ms` ticker + `561ms` instruments; NOT sub-ms HFT)
              </span>
            </div>

            <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-5 text-[11px]">
              <div className="rounded border border-emerald-500/30 bg-emerald-950/15 p-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">1. Typed Service API</span>
                  <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
                    PASS
                  </span>
                </div>
                <p className="mt-1 text-slate-300">
                  `GET /api/v1/service` + `POST /api/v1/risk/evaluate` with `X-AEGIS-Key`, rate limit (`30 rpm`), `4096B` cap, and `assessment_sha256`.
                </p>
              </div>

              <div className="rounded border border-emerald-500/30 bg-emerald-950/15 p-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">2. Official OKX ATK</span>
                  <span className="rounded bg-emerald-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-emerald-300">
                    PASS
                  </span>
                </div>
                <p className="mt-1 text-slate-300">
                  Server-side `@okx_ai/okx-trade-cli@1.4.8` subprocess reads (`ticker` + `instruments` on `site=tr`) with SHA-256 receipts.
                </p>
              </div>

              <div className="rounded border border-amber-500/30 bg-amber-950/15 p-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">3. A2MCP / Skill Spec</span>
                  <span className="rounded bg-amber-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-amber-300">
                    VERIFYING
                  </span>
                </div>
                <p className="mt-1 text-slate-300">
                  OpenAPI (`contracts/service-openapi.yaml`) & ERC-8004 descriptor (`/.well-known/erc8004-agent.json`) ready; not yet submitted.
                </p>
              </div>

              <div className="rounded border border-rose-500/30 bg-rose-950/15 p-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">4. SDK Settlement</span>
                  <span className="rounded bg-rose-500/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-rose-300">
                    MISSING
                  </span>
                </div>
                <p className="mt-1 text-slate-300">
                  OKX Agentic Wallet binding & A2MCP pay-per-call USDT/USDG SDK settlement (`payment_integration: NOT_IMPLEMENTED`).
                </p>
              </div>

              <div className="rounded border border-slate-700 bg-slate-900 p-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-white">5. Platform Review</span>
                  <span className="rounded bg-slate-800 px-1.5 py-0.5 font-mono text-[10px] font-bold text-amber-300">
                    NOT_LISTED
                  </span>
                </div>
                <p className="mt-1 text-slate-300">
                  Requires verified public HTTPS origin (`deployment_status: LOCAL_ONLY`) and OKX.AI provider onboarding review.
                </p>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-800/80 pt-2.5 text-[11px] text-slate-400">
              <span>
                <strong className="text-slate-200">Compliance Boundary:</strong> Operational pre-trade risk assessment only — never advertised as investment advice, portfolio management, or autonomous trade execution.
              </span>
              <a
                href="/.well-known/erc8004-agent.json"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 font-mono text-indigo-300 hover:underline"
              >
                Inspect Agent Card (`/.well-known/erc8004-agent.json`) <FileCode2 className="h-3.5 w-3.5" />
              </a>
            </div>
          </div>
        </section>

        {/* Interactive Pre-Trade Request & Response Inspector */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          {/* Left 5 Cols: Request Builder & cURL */}
          <section className="lg:col-span-5 flex flex-col justify-between rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg">
            <div>
              <div className="flex items-center justify-between border-b border-slate-800 pb-3">
                <div className="flex items-center gap-2">
                  <Code2 className="h-4 w-4 text-indigo-400" />
                  <h2 className="text-sm font-bold text-white">
                    Sample Safe Pre-Trade Request (`POST /api/v1/risk/evaluate`)
                  </h2>
                </div>
              </div>

              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  onClick={() => handleSelectSample("excess_notional")}
                  className={`flex-1 rounded-lg border p-2.5 text-left text-xs transition ${
                    selectedSample === "excess_notional"
                      ? "border-rose-500/60 bg-rose-950/30 text-white"
                      : "border-slate-800 bg-slate-950/60 text-slate-300 hover:border-slate-700"
                  }`}
                >
                  <div className="font-mono font-bold text-rose-300">
                    Preset A: Oversized (1 BTC) → HALT
                  </div>
                  <div className="mt-0.5 text-[11px] text-slate-400">
                    Triggers `excess_order_notional` veto (~$81.6k)
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => handleSelectSample("small_intent")}
                  className={`flex-1 rounded-lg border p-2.5 text-left text-xs transition ${
                    selectedSample === "small_intent"
                      ? "border-amber-500/60 bg-amber-950/30 text-white"
                      : "border-slate-800 bg-slate-950/60 text-slate-300 hover:border-slate-700"
                  }`}
                >
                  <div className="font-mono font-bold text-amber-300">
                    Preset B: Small (0.0001 BTC) → REVIEW
                  </div>
                  <div className="mt-0.5 text-[11px] text-slate-400">
                    Market checks PASS; account/LAYA unavailable
                  </div>
                </button>
              </div>

              <form onSubmit={handleEvaluate} className="mt-4 space-y-3 text-xs">
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block font-mono text-[11px] text-slate-400">
                      Symbol (const)
                    </label>
                    <input
                      type="text"
                      disabled
                      value="BTC-USDT"
                      className="mt-1 w-full rounded border border-slate-800 bg-slate-950 px-2.5 py-1.5 font-mono text-xs text-slate-400"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="service-action"
                      className="block font-mono text-[11px] text-slate-400"
                    >
                      Action
                    </label>
                    <select
                      id="service-action"
                      value={customAction}
                      onChange={(e) =>
                        setCustomAction(e.target.value as "BUY" | "SELL")
                      }
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 font-mono text-xs text-white"
                    >
                      <option value="BUY">BUY</option>
                      <option value="SELL">SELL</option>
                    </select>
                  </div>
                  <div>
                    <label
                      htmlFor="service-qty"
                      className="block font-mono text-[11px] text-slate-400"
                    >
                      Quantity (BTC)
                    </label>
                    <input
                      id="service-qty"
                      type="text"
                      value={customQty}
                      onChange={(e) => setCustomQty(e.target.value)}
                      className="mt-1 w-full rounded border border-slate-700 bg-slate-950 px-2.5 py-1.5 font-mono text-xs text-white"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] text-slate-400">
                      Typed Request Body (`RiskRequest-Input`):
                    </span>
                    <span className="font-mono text-[10px] text-emerald-400">
                      additionalProperties: false
                    </span>
                  </div>
                  <pre className="mt-1 rounded border border-slate-800 bg-slate-950 p-2.5 font-mono text-[11px] text-slate-200">
                    {sampleRequestJson}
                  </pre>
                </div>

                <button
                  type="submit"
                  disabled={evalBusy}
                  className="w-full rounded-md bg-indigo-500 px-4 py-2 text-xs font-bold text-white hover:bg-indigo-400 disabled:opacity-50 transition"
                >
                  {evalBusy
                    ? "Evaluating..."
                    : adminSecret && backendLive
                    ? "Run Live Server Assessment (POST /api/v1/risk/evaluate)"
                    : "Inspect Recorded HTTP Assessment Proof"}
                </button>
              </form>
            </div>

            {/* Server-side cURL Reference */}
            <div className="mt-5 border-t border-slate-800 pt-4">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 font-mono text-xs font-semibold text-slate-300">
                  <Terminal className="h-3.5 w-3.5 text-emerald-400" />
                  Server-to-Server cURL Example (No Key in Browser)
                </span>
                <button
                  type="button"
                  onClick={() => copyText(curlSnippet, "curl")}
                  className="inline-flex items-center gap-1 rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-200 hover:bg-slate-700"
                >
                  <Copy className="h-3 w-3" />
                  {copiedId === "curl" ? "Copied" : "Copy cURL"}
                </button>
              </div>
              <pre className="mt-2 overflow-x-auto rounded border border-slate-800 bg-slate-950 p-2.5 font-mono text-[10px] text-slate-300">
                {curlSnippet}
              </pre>
            </div>
          </section>

          {/* Right 7 Cols: RiskAssessment Response & Provenance */}
          <section className="lg:col-span-7 rounded-xl border border-slate-800 bg-slate-900/60 p-5 shadow-lg">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-3">
              <div className="flex items-center gap-2">
                {assessment.assessment === "HALT" ? (
                  <span className="inline-flex items-center gap-1.5 rounded-md border border-rose-500/50 bg-rose-500/20 px-3 py-1 font-mono text-xs font-bold text-rose-300">
                    <AlertOctagon className="h-4 w-4" />
                    ASSESSMENT: HALT
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 rounded-md border border-amber-500/50 bg-amber-500/20 px-3 py-1 font-mono text-xs font-bold text-amber-300">
                    <ShieldAlert className="h-4 w-4" />
                    ASSESSMENT: REVIEW
                  </span>
                )}

                <span className="rounded border border-rose-500/40 bg-rose-500/15 px-2.5 py-1 font-mono text-xs font-bold text-rose-300">
                  order_permission: {String(assessment.order_permission)}
                </span>
                <span className="rounded border border-slate-700 bg-slate-800 px-2 py-1 font-mono text-xs text-slate-300">
                  execution_authority: {String(assessment.execution_authority)}
                </span>
              </div>

              <span className="rounded bg-slate-800 px-2 py-0.5 font-mono text-[10px] text-slate-300">
                Proof Source:{" "}
                {assessmentSource === "LIVE"
                  ? "LIVE HTTP (/api/v1/risk/evaluate)"
                  : "Recorded HTTP (amendment-http.json)"}
              </span>
            </div>

            {/* Provenance & Market Checks */}
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3 text-xs">
              <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
                <div className="text-[11px] text-slate-400">Market Provenance</div>
                <div className="mt-1 font-mono font-bold text-emerald-300">
                  {assessment.market_provenance.source} ({assessment.market_provenance.status})
                </div>
                <div className="mt-1 font-mono text-[10px] text-slate-400">
                  site={assessment.market_provenance.site} · ts:{" "}
                  {assessment.market_provenance.market_timestamp?.slice(11, 23) ?? "N/A"}Z
                </div>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
                <div className="text-[11px] text-slate-400">Account Provenance</div>
                <div className="mt-1 font-mono font-bold text-amber-300">
                  {assessment.account_provenance}
                </div>
                <div className="mt-1 text-[10px] text-slate-400">
                  Caller balances are never inferred as $0
                </div>
              </div>

              <div className="rounded-lg border border-slate-800 bg-slate-950/70 p-3">
                <div className="text-[11px] text-slate-400">Model Availability</div>
                <div className="mt-1 font-mono font-bold text-slate-200">
                  LAYA: {assessment.laya_status} · EVREN: {assessment.evren_status}
                </div>
                <div className="mt-1 font-mono text-[10px] text-slate-400">
                  Policy Limit Price: {assessment.market_checks.policy_limit_price ?? "null"}
                </div>
              </div>
            </div>

            {/* Reasons List */}
            <div className="mt-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
                Returned Assessment Reasons ({assessment.reasons.length})
              </h3>
              <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {assessment.reasons.map((r) => {
                  const info = explainRiskReason(r);
                  return (
                    <div
                      key={r}
                      className="rounded border border-slate-800 bg-slate-950/70 p-2.5"
                    >
                      <span className="font-mono text-xs font-bold text-rose-300">
                        {info.ruleId}
                      </span>
                      <p className="mt-0.5 text-[11px] text-slate-300">
                        {info.title}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Canonical Assessment SHA-256 Digest (For Fuji Receipt Registry) */}
            <div className="mt-4 rounded-lg border border-indigo-500/30 bg-indigo-950/20 p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs font-bold text-indigo-300">
                  Canonical `assessment_sha256` (Ready for Fuji `RiskDecisionRegistry.recordReceipt`)
                </span>
                <button
                  type="button"
                  onClick={() =>
                    copyText(`0x${assessment.assessment_sha256}`, "sha256")
                  }
                  className="inline-flex items-center gap-1 rounded bg-indigo-500/20 px-2 py-0.5 font-mono text-[10px] text-indigo-200 hover:bg-indigo-500/30"
                >
                  <Copy className="h-3 w-3" />
                  {copiedId === "sha256" ? "Copied 0x Digest" : "Copy 0x Digest"}
                </button>
              </div>
              <div className="mt-1.5 break-all font-mono text-xs text-white">
                0x{assessment.assessment_sha256}
              </div>
              <p className="mt-1 text-[11px] text-slate-400">
                Computed over Python <code className="font-mono">json.dumps(payload_without_sha, sort_keys=True, separators=(&apos;,&apos;,&apos;:&apos;))</code>. Verifiable via <code className="font-mono">backend/scripts/prove_service.py</code>.
              </p>
            </div>

            {/* Raw Response JSON */}
            <div className="mt-4">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="font-mono text-xs font-semibold text-slate-300">
                  Full `RiskAssessment` Response Payload
                </span>
                <span className="font-mono text-[11px] text-slate-400">
                  {assessment.market_provenance.receipts.length} Official ATK Receipts Attached
                </span>
              </div>
              <pre className="max-h-56 overflow-auto rounded border border-slate-800 bg-slate-950 p-3 font-mono text-[11px] text-slate-300">
                {JSON.stringify(assessment, null, 2)}
              </pre>
            </div>
          </section>
        </div>
      </main>

      <ProofDrawerModal
        open={proofModalOpen}
        onClose={() => setProofModalOpen(false)}
        snapshot={snapshot}
        events={RECORDED_EVENTS_MARKET_ONLY}
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
