import { NextResponse } from "next/server";
import { fetchBackendJson } from "@/lib/server-backend";
import type { CostGateSummary } from "@/lib/types";

export const dynamic = "force-dynamic";

/** Proxy for the backend pre-trade cost gate summary; no fixture substitute when offline. */
export async function GET() {
  const res = await fetchBackendJson<CostGateSummary>("/api/metrics/cost-gate", { timeoutMs: 3500 });
  if (res.ok && res.data) {
    return NextResponse.json(res.data, {
      headers: { "X-AEGIS-Backend-Status": "LIVE" },
    });
  }
  return NextResponse.json(null, {
    status: 503,
    headers: {
      "X-AEGIS-Backend-Status": "UNAVAILABLE",
      "X-AEGIS-Backend-Error": res.error || "unreachable",
    },
  });
}
