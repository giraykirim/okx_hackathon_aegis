"use client";

import React from "react";
import {
  AlertOctagon,
  AlertTriangle,
  Building2,
  Code2,
  Copy,
  ExternalLink,
  FileCode2,
  ShieldAlert,
  ShieldCheck,
  Terminal,
} from "lucide-react";
import { AdminUnlockModal } from "@/components/AdminUnlockModal";
import { HeaderBar } from "@/components/HeaderBar";
import { ProofDrawerModal } from "@/components/ProofDrawerModal";
import {
  RECORDED_EVENTS_MARKET_ONLY,
  RECORDED_NOTIONAL_ASSESSMENTS,
  RECORDED_SERVICE_ASSESSMENTS,
  RECORDED_SERVICE_INFO,
  RECORDED_SNAPSHOT_MARKET_ONLY,
} from "@/lib/fixtures";
import type {
  NotionalRiskResponse,
  RiskAssessment,
  ServiceInfo,
  Snapshot,
} from "@/lib/types";
import { explainRiskReason, isResponseLive } from "@/lib/view-helpers";

export default function ServicePage() {
  const [snapshot] = React.useState<Snapshot>(RECORDED_SNAPSHOT_MARKET_ONLY);
  const [serviceInfo, setServiceInfo] = React.useState<ServiceInfo>(
    RECORDED_SERVICE_INFO
  );
  const [backendLive, setBackendLive] = React.useState(false);

  const [selectedSample, setSelectedSample] = React.useState<
    "small_intent" | "excess_notional"
  >("excess_notional");
  const [customAction, setCustomAction] = React.useState<"BUY" | "SELL">("BUY");
  const [customQty, setCustomQty] = React.useState<string>("1");
  const [evaluatedInputs10, setEvaluatedInputs10] = React.useState<{
    action: "BUY" | "SELL";
    qty: string;
  }>({ action: "BUY", qty: "1" });

  const [assessment, setAssessment] = React.useState<RiskAssessment>(
    RECORDED_SERVICE_ASSESSMENTS.excess_notional
  );
  const [assessmentSource, setAssessmentSource] = React.useState<
    "LIVE" | "RECORDED_PROOF"
  >("RECORDED_PROOF");
  const [evalBusy, setEvalBusy] = React.useState(false);
  const [assessmentError, setAssessmentError] = React.useState<string | null>(null);

  // Service 1.1.0 String-Notional Contract state (`contracts/PERSON3_HANDOFF.md`)
  const [notionalPreset, setNotionalPreset] = React.useState<
    "market_10_usdt" | "mock_10_usdt" | "excess_50_usdt"
  >("market_10_usdt");
  const [notionalAction, setNotionalAction] = React.useState<
    "BUY" | "SELL" | "NO_TRADE"
  >("BUY");
  const [notionalAmount, setNotionalAmount] = React.useState<string>("10");
  const [notionalReqId, setNotionalReqId] = React.useState<string>(
    "req-20261017-market-0001"
  );
  const [evaluatedInputs11, setEvaluatedInputs11] = React.useState<{
    reqId: string;
    action: "BUY" | "SELL" | "NO_TRADE";
    amount: string;
  }>({
    reqId: "req-20261017-market-0001",
    action: "BUY",
    amount: "10",
  });

  const [notionalRes, setNotionalRes] = React.useState<NotionalRiskResponse>(
    RECORDED_NOTIONAL_ASSESSMENTS.market_10_usdt
  );
  const [notionalSource, setNotionalSource] = React.useState<
    "LIVE" | "RECORDED_PROOF"
  >("RECORDED_PROOF");
  const [notionalBusy, setNotionalBusy] = React.useState(false);
  const [notionalError, setNotionalError] = React.useState<string | null>(null);

  const [proofModalOpen, setProofModalOpen] = React.useState(false);
  const [adminModalOpen, setAdminModalOpen] = React.useState(false);
  const [adminSecret, setAdminSecret] = React.useState("");
  const localOperator = React.useSyncExternalStore(
    () => () => {},
    () =>
      process.env.NODE_ENV === "development" &&
      (["127.0.0.1", "localhost", "[::1]"].includes(window.location.hostname) ||
        window.location.hostname.startsWith("192.168.") ||
        window.location.hostname.startsWith("10.") ||
        window.location.hostname.startsWith("172.")),
    () => false
  );
  const operatorUnlocked = localOperator || Boolean(adminSecret);
  const [copiedId, setCopiedId] = React.useState<string | null>(null);

  React.useEffect(() => {
    (async () => {
      try {
        const res = await fetch("/api/v1/service", { cache: "no-store" });
        const isLive = isResponseLive(res);
        setBackendLive(isLive);
        if (res.ok) {
          setServiceInfo((await res.json()) as ServiceInfo);
        }
      } catch {
        setBackendLive(false);
      }
    })();
  }, []);

  // Section 9 (P1-4): Detect when form inputs have diverged from the displayed evaluation
  const isAssessmentStale =
    customAction !== evaluatedInputs10.action ||
    customQty.trim() !== evaluatedInputs10.qty.trim();

  const isNotionalStale =
    notionalReqId.trim() !== evaluatedInputs11.reqId.trim() ||
    notionalAction !== evaluatedInputs11.action ||
    notionalAmount.trim() !== evaluatedInputs11.amount.trim();

  const handleSelectSample = (sample: "small_intent" | "excess_notional") => {
    setSelectedSample(sample);
    if (sample === "small_intent") {
      setCustomAction("BUY");
      setCustomQty("0.0001");
      setEvaluatedInputs10({ action: "BUY", qty: "0.0001" });
      setAssessment(RECORDED_SERVICE_ASSESSMENTS.small_intent);
    } else {
      setCustomAction("BUY");
      setCustomQty("1");
      setEvaluatedInputs10({ action: "BUY", qty: "1" });
      setAssessment(RECORDED_SERVICE_ASSESSMENTS.excess_notional);
    }
    setAssessmentSource("RECORDED_PROOF");
  };

  const handleEvaluate = async (e: React.FormEvent) => {
    e.preventDefault();
    setEvalBusy(true);
    setAssessmentError(null);
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
          client_request_id: `ui-eval-${Date.now()}`,
        }),
      });
      if (!res.ok) throw new Error(`Assessment failed (HTTP ${res.status}). Check operator access, input and service availability; no order was sent.`);
      if (res.ok) {
        const data = (await res.json()) as RiskAssessment;
        setAssessment(data);
        setEvaluatedInputs10({ action: customAction, qty: customQty });
        setAssessmentSource(
          isResponseLive(res) ? "LIVE" : "RECORDED_PROOF"
        );
      }
    } catch (error) {
      setAssessmentError(error instanceof Error ? error.message : "Assessment unavailable; no order was sent.");
    } finally {
      setEvalBusy(false);
    }
  };

  const handleSelectNotionalPreset = (
    preset: "market_10_usdt" | "mock_10_usdt" | "excess_50_usdt"
  ) => {
    setNotionalPreset(preset);
    setNotionalAction("BUY");
    if (preset === "excess_50_usdt") {
      setNotionalAmount("50");
      setNotionalReqId("req-20261017-market-0002");
      setEvaluatedInputs11({
        reqId: "req-20261017-market-0002",
        action: "BUY",
        amount: "50",
      });
    } else if (preset === "mock_10_usdt") {
      setNotionalAmount("10");
      setNotionalReqId("req-20261017-0001");
      setEvaluatedInputs11({
        reqId: "req-20261017-0001",
        action: "BUY",
        amount: "10",
      });
    } else {
      setNotionalAmount("10");
      setNotionalReqId("req-20261017-market-0001");
      setEvaluatedInputs11({
        reqId: "req-20261017-market-0001",
        action: "BUY",
        amount: "10",
      });
    }
    setNotionalRes(RECORDED_NOTIONAL_ASSESSMENTS[preset]);
    setNotionalSource("RECORDED_PROOF");
  };

  // Section 9 (P1-4): Handle NO_TRADE action vs notional value cleanly
  const handleNotionalActionChange = (
    nextAction: "BUY" | "SELL" | "NO_TRADE"
  ) => {
    setNotionalAction(nextAction);
    if (nextAction === "NO_TRADE") {
      setNotionalAmount("0");
    } else if (notionalAmount === "0") {
      setNotionalAmount("10");
    }
  };

  const handleEvaluateNotional = async (e: React.FormEvent) => {
    e.preventDefault();
    setNotionalBusy(true);
    setNotionalError(null);
    try {
      const effectiveNotional =
        notionalAction === "NO_TRADE" ? "0" : notionalAmount;
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
          request_id: notionalReqId,
          symbol: "BTC-USDT",
          proposed_action: notionalAction,
          proposed_notional: effectiveNotional,
          requester_context: null,
        }),
      });
      if (!res.ok) throw new Error(res.status === 409
        ? "Request ID already belongs to a different intent. Restore the original inputs or use a new request ID."
        : res.status === 429 ? "Service rate/concurrency limit reached. Wait before evaluating again; no order was sent."
        : `Evaluation unavailable (HTTP ${res.status}). Check input, operator access and backend availability; no order was sent.`);
      if (res.ok) {
        const data = (await res.json()) as NotionalRiskResponse;
        setNotionalRes(data);
        setEvaluatedInputs11({
          reqId: notionalReqId,
          action: notionalAction,
          amount: effectiveNotional,
        });
        setNotionalSource(
          isResponseLive(res) ? "LIVE" : "RECORDED_PROOF"
        );
      }
    } catch (error) {
      setNotionalError(error instanceof Error ? error.message : "Evaluation unavailable; no order was sent.");
    } finally {
      setNotionalBusy(false);
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
  --data '${JSON.stringify({
    symbol: "BTC-USDT",
    action: customAction,
    quantity: customQty,
    client_request_id: "agent-pretrade-check-01",
  })}'`;

  return (
    <div className="min-h-screen bg-[#0A0D10] text-[#E6EDF3]">
      <HeaderBar
        sourceMode={snapshot.source_mode}
        running={snapshot.running}
        backendLive={backendLive}
        sseState={backendLive ? "LIVE" : "FALLBACK"}
        lastCycleAt={snapshot.last_cycle_at}
        observedAt={assessment.market_provenance.market_timestamp}
        activeScenario={backendLive ? "live_backend" : "recorded_market_only"}
        onInspectProof={() => setProofModalOpen(true)}
        onOpenAdminModal={() => setAdminModalOpen(true)}
        adminUnlocked={operatorUnlocked}
      />

      <main className="mx-auto max-w-7xl space-y-5 px-4 py-6">
        {/* Hero / Positioning Card */}
        <section className="aegis-card-hero rounded-2xl p-6">
          <div className="flex flex-wrap items-start justify-between gap-4 border-b border-[#2A3542]/70 pb-4">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-[#4EE1C2]/35 bg-[#4EE1C2]/10 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-[#4EE1C2]">
                  GET /api/v1/service · POST /api/v1/risk/evaluate
                </span>
                <span className="rounded-full border border-[#EF4444]/35 bg-[#EF4444]/10 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-[#EF4444]">
                  order_permission=false · execution_authority=false
                </span>
                <span className="rounded-full border border-[#F59E0B]/35 bg-[#F59E0B]/10 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-[#F59E0B]">
                  OKX.AI compatible service — listing readiness not confirmed (
                  {serviceInfo.okx_ai.listing_status})
                </span>
              </div>
              <h1 className="mt-2.5 text-2xl font-bold tracking-tight text-[#E6EDF3]">
                {serviceInfo.name} (v{serviceInfo.version}) — Reusable Pre-Trade
                Risk Gate
              </h1>
              <p className="mt-1 max-w-3xl text-xs leading-relaxed text-[#9BA7B4]">
                {serviceInfo.purpose}. Target Customer:{" "}
                <strong className="text-[#E6EDF3]">
                  {serviceInfo.target_customer}
                </strong>
                . External trading agents call AEGIS before submitting an order;
                AEGIS fetches independent server-side OKX ATK market &
                instrument facts and applies deterministic sizing/freshness rules.
                The quantity API also requests LAYA/EVREN analysis and returns an
                assessment with a SHA-256 digest. The string-notional API returns
                an advisory verdict with evidence IDs; it does not call the models.
              </p>
            </div>

            <div className="rounded-xl border border-[#2A3542] bg-[#0A0D10]/85 p-3.5 font-mono text-xs text-[#9BA7B4]">
              <div>
                Deployment Status:{" "}
                <span className="font-bold text-[#F59E0B]">
                  {serviceInfo.deployment_status}
                </span>
              </div>
              <div className="mt-1">
                Public URL:{" "}
                <span className="text-[#6E7785]">
                  {serviceInfo.public_url ?? "null (No permanent public origin configured)"}
                </span>
              </div>
              <div className="mt-1">
                Auth Header:{" "}
                <span className="text-[#4EE1C2]">
                  {serviceInfo.auth.header}
                </span>{" "}
                ({serviceInfo.auth.requests_per_minute} req/min, max{" "}
                {serviceInfo.auth.max_request_bytes}B)
              </div>
            </div>
          </div>

          {/* Who Uses AEGIS + Business Model Hypothesis + OKX.AI Status */}
          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-3">
            {/* Target Customer */}
            <div className="rounded-xl border border-[#2A3542] bg-[#0A0D10]/70 p-4">
              <div className="flex items-center gap-2 text-xs font-bold text-[#E6EDF3]">
                <Building2 className="h-4 w-4 text-[#4EE1C2]" />
                Who Uses AEGIS & Problem Solved
              </div>
              <p className="mt-2 text-xs leading-relaxed text-[#9BA7B4]">
                Agentic trading teams often couple LLM prompts directly to
                exchange execution tools. A single hallucinated quantity, stale
                ticker, or duplicate retry causes unintended fills.
              </p>
              <ul className="mt-2 space-y-1 text-[11px] text-[#9BA7B4]">
                <li>
                  •{" "}
                  <strong className="text-[#E6EDF3]">
                    Untrusted Caller Input:
                  </strong>{" "}
                  Rejects caller-supplied balance/market flags (`HTTP 422`).
                </li>
                <li>
                  •{" "}
                  <strong className="text-[#E6EDF3]">
                    Server-Side ATK Provenance:
                  </strong>{" "}
                  Independently queries `@okx_ai/okx-trade-cli@1.4.8`.
                </li>
                <li>
                  •{" "}
                  <strong className="text-[#E6EDF3]">
                    Zero Trade Delegation:
                  </strong>{" "}
                  Never executes trades on the caller&apos;s behalf.
                </li>
              </ul>
            </div>

            {/* Commercial Business Model Hypothesis */}
            <div className="rounded-xl border border-[#F59E0B]/35 bg-[#F59E0B]/[0.06] p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#E6EDF3]">
                  Proposed Business Model
                </span>
                <span className="rounded border border-[#F59E0B]/40 bg-[#F59E0B]/15 px-2 py-0.5 font-mono text-[10px] font-bold text-[#F59E0B]">
                  HYPOTHESIS ({serviceInfo.pricing.status})
                </span>
              </div>
              <div className="mt-2.5 grid grid-cols-2 gap-2">
                <div className="rounded-lg border border-[#2A3542] bg-[#0A0D10]/80 p-2.5">
                  <div className="text-[10px] text-[#9BA7B4]">
                    Pay-Per-Assessment
                  </div>
                  <div className="mt-0.5 font-mono text-base font-bold text-[#4EE1C2]">
                    ${serviceInfo.pricing.per_assessment}{" "}
                    {serviceInfo.pricing.currency}
                  </div>
                  <div className="text-[10px] text-[#6E7785]">
                    per pre-trade check
                  </div>
                </div>
                <div className="rounded-lg border border-[#2A3542] bg-[#0A0D10]/80 p-2.5">
                  <div className="text-[10px] text-[#9BA7B4]">
                    B2B Team Tier
                  </div>
                  <div className="mt-0.5 font-mono text-base font-bold text-[#E6EDF3]">
                    ${serviceInfo.pricing.b2b_monthly}/mo
                  </div>
                  <div className="text-[10px] text-[#6E7785]">
                    {serviceInfo.pricing.included_assessments.toLocaleString()}{" "}
                    checks included
                  </div>
                </div>
              </div>
              <p className="mt-2 text-[11px] text-[#9BA7B4]">
                Payment integration:{" "}
                <code className="font-mono text-[#F59E0B]">
                  {serviceInfo.pricing.payment_integration}
                </code>
                . Commercial pricing hypothesis only — no billing rail, x402
                settlement, or revenue is claimed.
              </p>
            </div>

            {/* OKX.AI Marketplace Status */}
            <div className="rounded-xl border border-[#2A3542] bg-[#0A0D10]/70 p-4">
              <div className="flex items-center justify-between">
                <span className="text-xs font-bold text-[#E6EDF3]">
                  OKX.AI Service Compatibility
                </span>
                <span className="rounded border border-[#2A3542] bg-[#11161D] px-2 py-0.5 font-mono text-[10px] font-bold text-[#F59E0B]">
                  FEASIBILITY: {serviceInfo.okx_ai.integration_feasibility} ·{" "}
                  {serviceInfo.okx_ai.listing_status}
                </span>
              </div>
              <p className="mt-2 text-xs leading-relaxed text-[#9BA7B4]">
                OKX.AI compatible service — listing readiness not confirmed.
                Official OKX.AI operates on Onchain OS with Agent Marketplace &
                Task Marketplace, requiring an OKX Agentic Wallet, shared
                onchain Agent Identity, and A2MCP or A2A settlement.
              </p>
              <div className="mt-2.5 flex flex-wrap items-center justify-between gap-2 border-t border-[#2A3542]/70 pt-2 text-[11px]">
                <span className="font-mono text-[#6E7785]">
                  Listing URL:{" "}
                  {serviceInfo.okx_ai.verified_listing_url ?? "null"}
                </span>
                <div className="flex flex-wrap items-center gap-3">
                  <a
                    href="https://www.okx.com/learn/okx-ai"
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-[#4EE1C2] hover:underline"
                  >
                    OKX.AI Overview <ExternalLink className="h-3 w-3" />
                  </a>
                  <a
                    href={serviceInfo.okx_ai.requirements_url}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-1 text-[#4EE1C2] hover:underline"
                  >
                    Official ASP Docs <ExternalLink className="h-3 w-3" />
                  </a>
                </div>
              </div>
            </div>
          </div>

          {/* OKX.AI Provider Readiness Matrix */}
          <div className="mt-4 rounded-xl border border-[#2A3542] bg-[#0A0D10]/80 p-4">
            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#2A3542]/70 pb-2.5">
              <div className="flex items-center gap-2">
                <ShieldCheck className="h-4 w-4 text-[#4EE1C2]" />
                <h2 className="text-xs font-bold uppercase tracking-wider text-[#E6EDF3]">
                  OKX.AI Provider Readiness & SLA Transparency Matrix
                </h2>
              </div>
              <span className="font-mono text-[11px] text-[#F59E0B]">
                Measured timings are recorded per request in tool-call evidence;
                no latency SLA is established.
              </span>
            </div>

            <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2 lg:grid-cols-5 text-[11px]">
              <div className="rounded-lg border border-[#4EE1C2]/30 bg-[#4EE1C2]/[0.06] p-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#E6EDF3]">
                    1. Typed Service API
                  </span>
                  <span className="rounded bg-[#4EE1C2]/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-[#4EE1C2]">
                    PASS
                  </span>
                </div>
                <p className="mt-1 text-[#9BA7B4]">
                  `GET /api/v1/service` + `POST /api/v1/risk/evaluate` with
                  `X-AEGIS-Key`, rate limit ({serviceInfo.auth.requests_per_minute} rpm),
                  typed verdicts and evidence IDs. Quantity responses also carry a digest.
                </p>
              </div>

              <div className="rounded-lg border border-[#4EE1C2]/30 bg-[#4EE1C2]/[0.06] p-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#E6EDF3]">
                    2. Official OKX ATK
                  </span>
                  <span className="rounded bg-[#4EE1C2]/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-[#4EE1C2]">
                    PASS
                  </span>
                </div>
                <p className="mt-1 text-[#9BA7B4]">
                  Server-side official ATK MCP/CLI reads (`ticker` + `instruments`
                  on `site=tr`) with hashed evidence. Inspect the response receipts
                  for the transport actually used.
                </p>
              </div>

              <div className="rounded-lg border border-[#F59E0B]/30 bg-[#F59E0B]/[0.06] p-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#E6EDF3]">
                    3. A2MCP / Skill Spec
                  </span>
                  <span className="rounded bg-[#F59E0B]/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-[#F59E0B]">
                    VERIFYING
                  </span>
                </div>
                <p className="mt-1 text-[#9BA7B4]">
                  OpenAPI (`contracts/service-openapi.yaml`) & ERC-8004
                  descriptor (`/.well-known/erc8004-agent.json`) ready; not yet
                  submitted.
                </p>
              </div>

              <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/[0.06] p-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#E6EDF3]">
                    4. SDK Settlement
                  </span>
                  <span className="rounded bg-[#EF4444]/20 px-1.5 py-0.5 font-mono text-[10px] font-bold text-[#EF4444]">
                    MISSING
                  </span>
                </div>
                <p className="mt-1 text-[#9BA7B4]">
                  Paid x402 settlement is not implemented. It is unnecessary for
                  the proposed free pilot; marketplace caller authentication still
                  needs verification.
                </p>
              </div>

              <div className="rounded-lg border border-[#2A3542] bg-[#11161D] p-2.5">
                <div className="flex items-center justify-between">
                  <span className="font-semibold text-[#E6EDF3]">
                    5. Platform Review
                  </span>
                  <span className="rounded bg-[#1A222B] px-1.5 py-0.5 font-mono text-[10px] font-bold text-[#F59E0B]">
                    NOT_LISTED
                  </span>
                </div>
                <p className="mt-1 text-[#9BA7B4]">
                  Requires durable public HTTPS, a compliant endpoint and actual
                  provider registration/review. A temporary tunnel and wallet login
                  do not establish a listing.
                </p>
              </div>
            </div>

            <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-[#2A3542]/70 pt-2.5 text-[11px] text-[#9BA7B4]">
              <span>
                <strong className="text-[#E6EDF3]">Compliance Boundary:</strong>{" "}
                Operational pre-trade risk assessment only — never advertised as
                investment advice, portfolio management, or autonomous trade
                execution.
              </span>
              <a
                href="/.well-known/erc8004-agent.json"
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 font-mono text-[#4EE1C2] hover:underline"
              >
                Inspect ERC-8004 Metadata (`/.well-known/erc8004-agent.json`){" "}
                <FileCode2 className="h-3.5 w-3.5" />
              </a>
            </div>
          </div>
        </section>

        {/* Interactive Pre-Trade Request & Response Inspector */}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-12">
          {/* Left 5 Cols: Request Builder & cURL */}
          <section className="aegis-card lg:col-span-5 flex flex-col justify-between rounded-2xl p-5">
            <div>
              <div className="flex items-center justify-between border-b border-[#2A3542]/70 pb-3">
                <div className="flex items-center gap-2">
                  <Code2 className="h-4 w-4 text-[#4EE1C2]" />
                  <h2 className="text-sm font-bold text-[#E6EDF3]">
                    Sample Safe Pre-Trade Request (`POST /api/v1/risk/evaluate`)
                  </h2>
                </div>
              </div>

              <div className="mt-3 flex gap-2">
                <button
                  type="button"
                  onClick={() => handleSelectSample("excess_notional")}
                  className={`flex-1 rounded-xl border p-2.5 text-left text-xs transition ${
                    selectedSample === "excess_notional" && !isAssessmentStale
                      ? "border-[#EF4444]/60 bg-[#EF4444]/10 text-[#E6EDF3]"
                      : "border-[#2A3542] bg-[#0A0D10]/70 text-[#9BA7B4] hover:border-[#4EE1C2]/35"
                  }`}
                >
                  <div className="font-mono font-bold text-[#EF4444]">
                    Preset A: Oversized (1 BTC) → HALT
                  </div>
                  <div className="mt-0.5 text-[11px] text-[#9BA7B4]">
                    Triggers `excess_order_notional` veto (~$81.6k)
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => handleSelectSample("small_intent")}
                  className={`flex-1 rounded-xl border p-2.5 text-left text-xs transition ${
                    selectedSample === "small_intent" && !isAssessmentStale
                      ? "border-[#F59E0B]/60 bg-[#F59E0B]/10 text-[#E6EDF3]"
                      : "border-[#2A3542] bg-[#0A0D10]/70 text-[#9BA7B4] hover:border-[#4EE1C2]/35"
                  }`}
                >
                  <div className="font-mono font-bold text-[#F59E0B]">
                    Preset B: Small (0.0001 BTC) → REVIEW
                  </div>
                  <div className="mt-0.5 text-[11px] text-[#9BA7B4]">
                    Market checks PASS; account/LAYA unavailable
                  </div>
                </button>
              </div>

              <form
                onSubmit={handleEvaluate}
                className="mt-4 space-y-3 text-xs"
              >
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="block font-mono text-[11px] text-[#9BA7B4]">
                      Symbol (const)
                    </label>
                    <input
                      type="text"
                      disabled
                      value="BTC-USDT"
                      className="mt-1 w-full rounded-lg border border-[#2A3542] bg-[#0A0D10] px-2.5 py-1.5 font-mono text-xs text-[#6E7785]"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="service-action"
                      className="block font-mono text-[11px] text-[#9BA7B4]"
                    >
                      Action
                    </label>
                    <select
                      id="service-action"
                      value={customAction}
                      onChange={(e) =>
                        setCustomAction(e.target.value as "BUY" | "SELL")
                      }
                      className="mt-1 w-full rounded-lg border border-[#2A3542] bg-[#0A0D10] px-2.5 py-1.5 font-mono text-xs text-[#E6EDF3]"
                    >
                      <option value="BUY">BUY</option>
                      <option value="SELL">SELL</option>
                    </select>
                  </div>
                  <div>
                    <label
                      htmlFor="service-qty"
                      className="block font-mono text-[11px] text-[#9BA7B4]"
                    >
                      Quantity (BTC)
                    </label>
                    <input
                      id="service-qty"
                      type="text"
                      value={customQty}
                      onChange={(e) => setCustomQty(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-[#2A3542] bg-[#0A0D10] px-2.5 py-1.5 font-mono text-xs text-[#E6EDF3]"
                    />
                  </div>
                </div>

                <div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] text-[#9BA7B4]">
                      Typed Request Body (`RiskRequest-Input`):
                    </span>
                    <span className="font-mono text-[10px] text-[#4EE1C2]">
                      additionalProperties: false
                    </span>
                  </div>
                  <pre className="mt-1 rounded-lg border border-[#2A3542] bg-[#0A0D10] p-2.5 font-mono text-[11px] text-[#E6EDF3]">
                    {sampleRequestJson}
                  </pre>
                </div>

                <button
                  type="submit"
                  disabled={evalBusy}
                  className="w-full rounded-xl bg-[#4EE1C2] px-4 py-2 text-xs font-bold text-[#0A0D10] hover:bg-[#4EE1C2]/90 disabled:opacity-50 transition"
                >
                  {evalBusy
                    ? "Evaluating..."
                    : adminSecret && backendLive
                    ? "Run Live Server Assessment (POST /api/v1/risk/evaluate)"
                    : "Run Pre-Trade Assessment"}
                </button>
                {assessmentError && <p role="alert" className="text-xs text-[#F59E0B]">{assessmentError}</p>}
              </form>
            </div>

            {/* Server-side cURL Reference */}
            <div className="mt-5 border-t border-[#2A3542]/70 pt-4">
              <div className="flex items-center justify-between">
                <span className="inline-flex items-center gap-1.5 font-mono text-xs font-semibold text-[#9BA7B4]">
                  <Terminal className="h-3.5 w-3.5 text-[#4EE1C2]" />
                  Server-to-Server cURL Example (No Key in Browser)
                </span>
                <button
                  type="button"
                  onClick={() => copyText(curlSnippet, "curl")}
                  className="inline-flex items-center gap-1 rounded border border-[#2A3542] bg-[#11161D] px-2 py-0.5 font-mono text-[10px] text-[#E6EDF3] hover:border-[#4EE1C2]/40"
                >
                  <Copy className="h-3 w-3" />
                  {copiedId === "curl" ? "Copied" : "Copy cURL"}
                </button>
              </div>
              <pre className="mt-2 overflow-x-auto rounded-lg border border-[#2A3542] bg-[#0A0D10] p-2.5 font-mono text-[10px] text-[#9BA7B4]">
                {curlSnippet}
              </pre>
            </div>
          </section>

          {/* Right 7 Cols: RiskAssessment Response & Provenance */}
          <section className="aegis-card lg:col-span-7 rounded-2xl p-5">
            {/* Section 9 (P1-4): Stale Evaluation Warning when inputs changed */}
            {isAssessmentStale && (
              <div className="mb-3 flex items-center justify-between gap-2 rounded-xl border border-[#F59E0B]/45 bg-[#F59E0B]/12 px-3.5 py-2.5 text-xs text-[#F59E0B]">
                <span className="inline-flex items-center gap-2 font-mono font-semibold">
                  <AlertTriangle className="h-4 w-4 shrink-0" />
                  Previous Evaluation — Inputs Changed
                </span>
                <span className="text-[11px] text-[#E6EDF3]/90">
                  Displaying evaluation for {evaluatedInputs10.action}{" "}
                  {evaluatedInputs10.qty} BTC. Submit form to recompute.
                </span>
              </div>
            )}

            <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#2A3542]/70 pb-3">
              <div className="flex flex-wrap items-center gap-2">
                {assessment.assessment === "HALT" ? (
                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-[#EF4444]/50 bg-[#EF4444]/15 px-3 py-1 font-mono text-xs font-bold text-[#EF4444]">
                    <AlertOctagon className="h-4 w-4" />
                    ASSESSMENT: HALT
                  </span>
                ) : (
                  <span className="inline-flex items-center gap-1.5 rounded-lg border border-[#F59E0B]/50 bg-[#F59E0B]/15 px-3 py-1 font-mono text-xs font-bold text-[#F59E0B]">
                    <ShieldAlert className="h-4 w-4" />
                    ASSESSMENT: REVIEW
                  </span>
                )}

                <span className="rounded-lg border border-[#EF4444]/40 bg-[#EF4444]/10 px-2.5 py-1 font-mono text-xs font-bold text-[#EF4444]">
                  order_permission: {String(assessment.order_permission)}
                </span>
                <span className="rounded-lg border border-[#2A3542] bg-[#11161D] px-2 py-1 font-mono text-xs text-[#9BA7B4]">
                  execution_authority: {String(assessment.execution_authority)}
                </span>
              </div>

              <span className="rounded border border-[#2A3542] bg-[#11161D] px-2 py-0.5 font-mono text-[10px] text-[#9BA7B4]">
                Source:{" "}
                {assessmentSource === "LIVE"
                  ? "Live HTTP (/api/v1/risk/evaluate)"
                  : "Recorded HTTP Evidence (amendment-http.json)"}
              </span>
            </div>

            {/* Provenance & Market Checks */}
            <div className="mt-4 grid grid-cols-1 gap-3 sm:grid-cols-3 text-xs">
              <div className="rounded-xl border border-[#2A3542] bg-[#0A0D10]/70 p-3">
                <div className="text-[11px] text-[#9BA7B4]">
                  Market Provenance
                </div>
                <div className="mt-1 font-mono font-bold text-[#4EE1C2]">
                  {assessment.market_provenance.source} (
                  {assessment.market_provenance.status})
                </div>
                <div className="mt-1 font-mono text-[10px] text-[#6E7785]">
                  site={assessment.market_provenance.site} · ts:{" "}
                  {assessment.market_provenance.market_timestamp?.slice(
                    11,
                    23
                  ) ?? "N/A"}
                  Z
                </div>
              </div>

              <div className="rounded-xl border border-[#2A3542] bg-[#0A0D10]/70 p-3">
                <div className="text-[11px] text-[#9BA7B4]">
                  Account Provenance
                </div>
                <div className="mt-1 font-mono font-bold text-[#F59E0B]">
                  {assessment.account_provenance}
                </div>
                <div className="mt-1 text-[10px] text-[#6E7785]">
                  Caller balances are never inferred as $0
                </div>
              </div>

              <div className="rounded-xl border border-[#2A3542] bg-[#0A0D10]/70 p-3">
                <div className="text-[11px] text-[#9BA7B4]">
                  Model Availability
                </div>
                <div className="mt-1 font-mono font-bold text-[#E6EDF3]">
                  LAYA: {assessment.laya_status} · EVREN:{" "}
                  {assessment.evren_status}
                </div>
                <div className="mt-1 font-mono text-[10px] text-[#6E7785]">
                  Policy Limit Price:{" "}
                  {assessment.market_checks.policy_limit_price ?? "null"}
                </div>
              </div>
            </div>

            {/* Reasons List */}
            <div className="mt-4">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-[#9BA7B4]">
                Returned Assessment Reasons ({assessment.reasons.length})
              </h3>
              <div className="mt-2 grid grid-cols-1 gap-2 sm:grid-cols-2">
                {assessment.reasons.map((r) => {
                  const info = explainRiskReason(r);
                  return (
                    <div
                      key={r}
                      className="rounded-xl border border-[#2A3542] bg-[#0A0D10]/70 p-2.5"
                    >
                      <span className="font-mono text-xs font-bold text-[#EF4444]">
                        {info.ruleId}
                      </span>
                      <p className="mt-0.5 text-[11px] text-[#9BA7B4]">
                        {info.title}
                      </p>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Canonical Assessment SHA-256 Digest */}
            <div className="mt-4 rounded-xl border border-[#4EE1C2]/30 bg-[#4EE1C2]/[0.06] p-3">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="font-mono text-xs font-bold text-[#4EE1C2]">
                  Canonical `assessment_sha256` (Local Audit Digest)
                </span>
                <button
                  type="button"
                  onClick={() =>
                    copyText(`0x${assessment.assessment_sha256}`, "sha256")
                  }
                  className="inline-flex items-center gap-1 rounded border border-[#4EE1C2]/40 bg-[#4EE1C2]/15 px-2 py-0.5 font-mono text-[10px] text-[#4EE1C2] hover:bg-[#4EE1C2]/25"
                >
                  <Copy className="h-3 w-3" />
                  {copiedId === "sha256"
                    ? "Copied 0x Digest"
                    : "Copy 0x Digest"}
                </button>
              </div>
              <div className="mt-1.5 break-all font-mono text-xs text-[#E6EDF3]">
                0x{assessment.assessment_sha256}
              </div>
            </div>

            {/* Raw Response JSON */}
            <div className="mt-4">
              <div className="mb-1.5 flex items-center justify-between">
                <span className="font-mono text-xs font-semibold text-[#9BA7B4]">
                  Full `RiskAssessment` Response Payload
                </span>
                <span className="font-mono text-[11px] text-[#6E7785]">
                  {assessment.market_provenance.receipts.length} Official ATK
                  Receipts Attached
                </span>
              </div>
              <pre className="max-h-56 overflow-auto rounded-xl border border-[#2A3542] bg-[#0A0D10] p-3 font-mono text-[11px] text-[#9BA7B4]">
                {JSON.stringify(assessment, null, 2)}
              </pre>
            </div>
          </section>
        </div>

        {/* Service 1.1.0 String-Notional Contract Inspector (`contracts/PERSON3_HANDOFF.md`) */}
        <section className="aegis-card rounded-2xl p-6">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-[#2A3542]/70 pb-3">
            <div>
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full border border-[#4EE1C2]/35 bg-[#4EE1C2]/10 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-[#4EE1C2]">
                  SERVICE 1.1.0 STRING-NOTIONAL CONTRACT
                </span>
                <span className="rounded-full border border-[#EF4444]/35 bg-[#EF4444]/10 px-2.5 py-0.5 font-mono text-[10px] font-semibold text-[#EF4444]">
                  execution_authorized: {String(notionalRes.execution_authorized)}
                </span>
                <span className="rounded-full border border-[#2A3542] bg-[#11161D] px-2.5 py-0.5 font-mono text-[10px] text-[#9BA7B4]">
                  chain_receipt: {String(notionalRes.chain_receipt)}
                </span>
              </div>
              <h2 className="mt-2 text-base font-bold text-[#E6EDF3]">
                String-Notional Request (`
                {`{request_id, symbol, proposed_action, proposed_notional, requester_context}`}
                `) → 9-Field Verdict
              </h2>
              <p className="text-xs text-[#9BA7B4]">
                Idempotent correlation by `request_id` + effective intent;
                renders `UNAVAILABLE` / `BLOCK` explicitly with
                `execution_authorized=false` and `chain_receipt=null`.
              </p>
            </div>
            <span className="rounded border border-[#2A3542] bg-[#11161D] px-2.5 py-1 font-mono text-[10px] text-[#9BA7B4]">
              Source:{" "}
              {notionalSource === "LIVE"
                ? "Live HTTP (/api/v1/risk/evaluate)"
                : "Recorded HTTP Evidence"}
            </span>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-12">
            <div className="lg:col-span-5 space-y-3 text-xs">
              <div className="grid grid-cols-3 gap-2">
                <button
                  type="button"
                  onClick={() => handleSelectNotionalPreset("market_10_usdt")}
                  className={`rounded-xl border p-2.5 text-left transition ${
                    notionalPreset === "market_10_usdt" && !isNotionalStale
                      ? "border-[#F59E0B]/60 bg-[#F59E0B]/10 text-[#E6EDF3]"
                      : "border-[#2A3542] bg-[#0A0D10]/70 text-[#9BA7B4]"
                  }`}
                >
                  <div className="font-mono text-[11px] font-bold text-[#F59E0B]">
                    $10 MARKET_ONLY
                  </div>
                  <div className="mt-0.5 text-[10px] text-[#9BA7B4]">
                    → `UNAVAILABLE`
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => handleSelectNotionalPreset("mock_10_usdt")}
                  className={`rounded-xl border p-2.5 text-left transition ${
                    notionalPreset === "mock_10_usdt" && !isNotionalStale
                      ? "border-[#4EE1C2]/60 bg-[#4EE1C2]/10 text-[#E6EDF3]"
                      : "border-[#2A3542] bg-[#0A0D10]/70 text-[#9BA7B4]"
                  }`}
                >
                  <div className="font-mono text-[11px] font-bold text-[#4EE1C2]">
                    $10 MOCK Fixture
                  </div>
                  <div className="mt-0.5 text-[10px] text-[#9BA7B4]">
                    → `UNAVAILABLE`
                  </div>
                </button>

                <button
                  type="button"
                  onClick={() => handleSelectNotionalPreset("excess_50_usdt")}
                  className={`rounded-xl border p-2.5 text-left transition ${
                    notionalPreset === "excess_50_usdt" && !isNotionalStale
                      ? "border-[#EF4444]/60 bg-[#EF4444]/10 text-[#E6EDF3]"
                      : "border-[#2A3542] bg-[#0A0D10]/70 text-[#9BA7B4]"
                  }`}
                >
                  <div className="font-mono text-[11px] font-bold text-[#EF4444]">
                    $50 Oversized
                  </div>
                  <div className="mt-0.5 text-[10px] text-[#9BA7B4]">
                    → `BLOCK` (&gt;$25 cap)
                  </div>
                </button>
              </div>

              <form onSubmit={handleEvaluateNotional} className="space-y-2.5">
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label
                      htmlFor="notional-req-id"
                      className="block font-mono text-[11px] text-[#9BA7B4]"
                    >
                      request_id
                    </label>
                    <input
                      id="notional-req-id"
                      type="text"
                      value={notionalReqId}
                      onChange={(e) => setNotionalReqId(e.target.value)}
                      className="mt-1 w-full rounded-lg border border-[#2A3542] bg-[#0A0D10] px-2 py-1.5 font-mono text-[11px] text-[#E6EDF3]"
                    />
                  </div>
                  <div>
                    <label
                      htmlFor="notional-action"
                      className="block font-mono text-[11px] text-[#9BA7B4]"
                    >
                      proposed_action
                    </label>
                    <select
                      id="notional-action"
                      value={notionalAction}
                      onChange={(e) =>
                        handleNotionalActionChange(
                          e.target.value as "BUY" | "SELL" | "NO_TRADE"
                        )
                      }
                      className="mt-1 w-full rounded-lg border border-[#2A3542] bg-[#0A0D10] px-2 py-1.5 font-mono text-[11px] text-[#E6EDF3]"
                    >
                      <option value="BUY">BUY</option>
                      <option value="SELL">SELL</option>
                      <option value="NO_TRADE">NO_TRADE</option>
                    </select>
                  </div>
                  <div>
                    <label
                      htmlFor="notional-amount"
                      className="block font-mono text-[11px] text-[#9BA7B4]"
                    >
                      proposed_notional (USDT)
                    </label>
                    <input
                      id="notional-amount"
                      type="text"
                      disabled={notionalAction === "NO_TRADE"}
                      value={
                        notionalAction === "NO_TRADE" ? "0" : notionalAmount
                      }
                      onChange={(e) => setNotionalAmount(e.target.value)}
                      className={`mt-1 w-full rounded-lg border px-2 py-1.5 font-mono text-[11px] ${
                        notionalAction === "NO_TRADE"
                          ? "border-[#2A3542]/60 bg-[#11161D] text-[#6E7785] cursor-not-allowed"
                          : "border-[#2A3542] bg-[#0A0D10] text-[#E6EDF3]"
                      }`}
                    />
                  </div>
                </div>

                {notionalAction === "NO_TRADE" && (
                  <div className="rounded-lg border border-[#2A3542] bg-[#11161D] px-2.5 py-1.5 font-mono text-[11px] text-[#9BA7B4]">
                    NO_TRADE selected: proposed_notional is locked to{" "}
                    <span className="text-[#4EE1C2]">0 USDT</span>{" "}
                    (non-executable idle check).
                  </div>
                )}

                <pre className="rounded-lg border border-[#2A3542] bg-[#0A0D10] p-2.5 font-mono text-[11px] text-[#E6EDF3]">
                  {JSON.stringify(
                    {
                      request_id: notionalReqId,
                      symbol: "BTC-USDT",
                      proposed_action: notionalAction,
                      proposed_notional:
                        notionalAction === "NO_TRADE" ? "0" : notionalAmount,
                      requester_context: null,
                    },
                    null,
                    2
                  )}
                </pre>

                <button
                  type="submit"
                  disabled={notionalBusy}
                  className="w-full rounded-xl bg-[#4EE1C2] px-4 py-2 text-xs font-bold text-[#0A0D10] hover:bg-[#4EE1C2]/90 disabled:opacity-50 transition"
                >
                  {notionalBusy
                    ? "Evaluating Service 1.1.0..."
                    : "Evaluate String-Notional Contract (Service 1.1.0)"}
                </button>
                {notionalError && <p role="alert" className="text-xs text-[#F59E0B]">{notionalError}</p>}
              </form>
            </div>

            <div className="lg:col-span-7 space-y-3 text-xs">
              {/* Section 9 (P1-4): Stale Evaluation Warning when Service 1.1.0 inputs changed */}
              {isNotionalStale && (
                <div className="flex items-center justify-between gap-2 rounded-xl border border-[#F59E0B]/45 bg-[#F59E0B]/12 px-3.5 py-2.5 text-xs text-[#F59E0B]">
                  <span className="inline-flex items-center gap-2 font-mono font-semibold">
                    <AlertTriangle className="h-4 w-4 shrink-0" />
                    Previous Evaluation — Inputs Changed
                  </span>
                  <span className="text-[11px] text-[#E6EDF3]/90">
                    Displaying evaluation for {evaluatedInputs11.action} $
                    {evaluatedInputs11.amount} USDT. Click Evaluate to
                    recompute.
                  </span>
                </div>
              )}

              <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-[#2A3542] bg-[#0A0D10]/80 p-3">
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-lg px-2.5 py-1 font-mono text-xs font-bold ${
                      notionalRes.verdict === "BLOCK"
                        ? "bg-[#EF4444]/15 text-[#EF4444] border border-[#EF4444]/40"
                        : "bg-[#F59E0B]/15 text-[#F59E0B] border border-[#F59E0B]/40"
                    }`}
                  >
                    VERDICT: {notionalRes.verdict}
                  </span>
                  <span className="rounded-lg bg-[#EF4444]/10 px-2.5 py-1 font-mono text-xs font-bold text-[#EF4444] border border-[#EF4444]/30">
                    execution_authorized:{" "}
                    {String(notionalRes.execution_authorized)}
                  </span>
                </div>
                <span className="font-mono text-[11px] text-[#9BA7B4]">
                  policy_version: {notionalRes.policy_version} · mode:{" "}
                  {notionalRes.source_mode}
                </span>
              </div>

              <div className="flex flex-wrap gap-1.5">
                {notionalRes.reason_codes.map((code) => (
                  <span
                    key={code}
                    className="rounded-md border border-[#2A3542] bg-[#0A0D10] px-2 py-1 font-mono text-[11px] text-[#F59E0B]"
                  >
                    {code}
                  </span>
                ))}
              </div>

              <pre className="max-h-52 overflow-auto rounded-xl border border-[#2A3542] bg-[#0A0D10] p-3 font-mono text-[11px] text-[#9BA7B4]">
                {JSON.stringify(notionalRes, null, 2)}
              </pre>
            </div>
          </div>
        </section>
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
