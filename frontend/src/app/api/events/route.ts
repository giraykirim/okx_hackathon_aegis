import { NextRequest, NextResponse } from "next/server";
import { RECORDED_EVENTS_MARKET_ONLY } from "@/lib/fixtures";
import { fetchBackendJson } from "@/lib/server-backend";
import type { EventItem } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET(request: NextRequest) {
  const limitParam = request.nextUrl.searchParams.get("limit") || "100";
  const limit = Math.min(Math.max(parseInt(limitParam, 10) || 100, 1), 1000);
  const res = await fetchBackendJson<EventItem[]>(`/api/events?limit=${limit}`, {
    timeoutMs: 4000,
  });
  if (res.ok && res.data) {
    return NextResponse.json(res.data, {
      headers: {
        "X-AEGIS-Backend-Status": "LIVE",
      },
    });
  }
  return NextResponse.json(RECORDED_EVENTS_MARKET_ONLY.slice(-limit), {
    headers: {
      "X-AEGIS-Backend-Status": "OFFLINE_FIXTURE",
      "X-AEGIS-Backend-Error": res.error || "unreachable",
    },
  });
}
