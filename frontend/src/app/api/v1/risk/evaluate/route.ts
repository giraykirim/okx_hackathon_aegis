import { NextResponse } from "next/server";
import {
  RECORDED_NOTIONAL_ASSESSMENTS,
  RECORDED_SERVICE_ASSESSMENTS,
} from "@/lib/fixtures";
import { fetchBackendJson, isAdminAuthorized } from "@/lib/server-backend";
import type { NotionalRiskResponse, RiskAssessment } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let body: {
    symbol?: string;
    action?: string;
    quantity?: string | number;
    client_request_id?: string | null;
    request_id?: string;
    proposed_action?: string;
    proposed_notional?: string;
    requester_context?: Record<string, unknown> | null;
  } = {};

  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON payload" }, { status: 400 });
  }
  if (body === null || typeof body !== "object" || Array.isArray(body)) {
    return NextResponse.json({ detail: "Expected a JSON object" }, { status: 400 });
  }

  const isNotionalContract = typeof body.proposed_notional === "string";

  // Only allow live backend evaluation when operator admin secret + service key are configured
  const serviceKey = process.env.AEGIS_SERVICE_API_KEY;
  const adminCheck = isAdminAuthorized(request);

  if (serviceKey && adminCheck.authorized) {
    const res = await fetchBackendJson<RiskAssessment | NotionalRiskResponse>(
      "/api/v1/risk/evaluate",
      {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          "X-AEGIS-Key": serviceKey,
        },
        body: JSON.stringify(body),
        // Backend assessment has a 30s total budget plus a bounded body read.
        timeoutMs: 40000,
      }
    );

    if (res.ok && res.data) {
      return NextResponse.json(res.data, {
        headers: {
          "X-AEGIS-Backend-Status": "LIVE",
        },
      });
    }
    return NextResponse.json(
      { detail: res.error || "Live risk evaluation failed" },
      { status: res.status || 503 }
    );
  }

  if (isNotionalContract) {
    const notionalNum = Number(body.proposed_notional ?? 0);
    const selectedNotional =
      notionalNum > 25
        ? RECORDED_NOTIONAL_ASSESSMENTS.excess_50_usdt
        : body.request_id === "mock-notional-fixture-001"
        ? RECORDED_NOTIONAL_ASSESSMENTS.mock_10_usdt
        : RECORDED_NOTIONAL_ASSESSMENTS.market_10_usdt;

    return NextResponse.json(selectedNotional, {
      headers: {
        "X-AEGIS-Backend-Status": "RECORDED_PROOF",
        "X-AEGIS-Proof-Source": "backend/evidence/notional-market-http.json",
      },
    });
  }

  // View-only Judge mode (Legacy Quantity Contract): return recorded real HTTP proof from `backend/evidence/amendment-http.json`
  const qtyNum = Number(body.quantity ?? 0);
  const selected =
    qtyNum >= 0.5
      ? RECORDED_SERVICE_ASSESSMENTS.excess_notional
      : RECORDED_SERVICE_ASSESSMENTS.small_intent;

  return NextResponse.json(selected, {
    headers: {
      "X-AEGIS-Backend-Status": "RECORDED_PROOF",
      "X-AEGIS-Proof-Source": "backend/evidence/amendment-http.json",
    },
  });
}
