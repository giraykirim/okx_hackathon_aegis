import { NextResponse } from "next/server";
import { RECORDED_METRICS_MARKET_ONLY } from "@/lib/fixtures";
import { fetchBackendJson } from "@/lib/server-backend";
import type { Metrics } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  const res = await fetchBackendJson<Metrics>("/api/metrics", { timeoutMs: 3500 });
  if (res.ok && res.data) {
    return NextResponse.json(res.data, {
      headers: {
        "X-AEGIS-Backend-Status": "LIVE",
      },
    });
  }
  return NextResponse.json(RECORDED_METRICS_MARKET_ONLY, {
    headers: {
      "X-AEGIS-Backend-Status": "OFFLINE_FIXTURE",
      "X-AEGIS-Backend-Error": res.error || "unreachable",
    },
  });
}
