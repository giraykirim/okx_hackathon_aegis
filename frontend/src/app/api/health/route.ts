import { NextResponse } from "next/server";
import { RECORDED_HEALTH_MARKET_ONLY } from "@/lib/fixtures";
import { fetchBackendJson } from "@/lib/server-backend";
import type { Health } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  const res = await fetchBackendJson<Health>("/api/health", { timeoutMs: 3500 });
  if (res.ok && res.data) {
    return NextResponse.json(res.data, {
      headers: {
        "X-AEGIS-Backend-Status": "LIVE",
      },
    });
  }
  return NextResponse.json(RECORDED_HEALTH_MARKET_ONLY, {
    headers: {
      "X-AEGIS-Backend-Status": "OFFLINE_FIXTURE",
      "X-AEGIS-Backend-Error": res.error || "unreachable",
    },
  });
}
