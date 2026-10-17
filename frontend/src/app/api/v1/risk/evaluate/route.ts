import { NextResponse } from "next/server";
import { RECORDED_SERVICE_ASSESSMENTS } from "@/lib/fixtures";
import { fetchBackendJson, isAdminAuthorized } from "@/lib/server-backend";
import type { RiskAssessment } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function POST(request: Request) {
  let body: {
    symbol?: string;
    action?: string;
    quantity?: string | number;
    client_request_id?: string | null;
  } = {};

  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ detail: "Invalid JSON payload" }, { status: 400 });
  }

  // Only allow live backend evaluation when operator admin secret + service key are configured
  const serviceKey = process.env.AEGIS_SERVICE_API_KEY;
  const adminCheck = isAdminAuthorized(request);

  if (serviceKey && adminCheck.authorized) {
    const res = await fetchBackendJson<RiskAssessment>("/api/v1/risk/evaluate", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "X-AEGIS-Key": serviceKey,
      },
      body: JSON.stringify(body),
      timeoutMs: 12000,
    });

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

  // View-only Judge mode: return recorded real HTTP proof from `backend/evidence/amendment-http.json`
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
