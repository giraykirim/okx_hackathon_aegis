import { NextRequest, NextResponse } from "next/server";
import { RECORDED_SNAPSHOT_MARKET_ONLY } from "@/lib/fixtures";
import { fetchBackendJson } from "@/lib/server-backend";
import type { Decision } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const limitParam = request.nextUrl.searchParams.get("limit") || "50";
  const limit = Math.min(Math.max(parseInt(limitParam, 10) || 50, 1), 500);
  const res = await fetchBackendJson<Decision[]>(`/api/decisions?limit=${limit}`, {
    timeoutMs: 4000,
  });
  if (res.ok && res.data) {
    return NextResponse.json(res.data, {
      headers: {
        "X-AEGIS-Backend-Status": "LIVE",
      },
    });
  }

  const fallbackDecisions: Decision[] = RECORDED_SNAPSHOT_MARKET_ONLY.latest_decision
    ? [RECORDED_SNAPSHOT_MARKET_ONLY.latest_decision]
    : [];
  return NextResponse.json(fallbackDecisions.slice(0, limit), {
    headers: {
      "X-AEGIS-Backend-Status": "OFFLINE_FIXTURE",
      "X-AEGIS-Backend-Error": res.error || "unreachable",
    },
  });
}
