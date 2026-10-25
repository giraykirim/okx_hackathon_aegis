import { NextResponse } from "next/server";
import { fetchBackendJson } from "@/lib/server-backend";
import type { DemoPnl } from "@/lib/types";

export const dynamic = "force-dynamic";

/**
 * Proxy for the additive backend `/api/metrics/pnl`. `null` from the backend means "no
 * agent-owned verified fills" and is passed through as live data. When the backend is
 * unreachable no recorded fixture is substituted: PnL is never shown without a live source.
 */
export async function GET() {
  const res = await fetchBackendJson<DemoPnl | null>("/api/metrics/pnl", { timeoutMs: 3500 });
  if (res.ok) {
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
