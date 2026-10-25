import { NextResponse } from "next/server";
import { fetchBackendJson } from "@/lib/server-backend";
import type { ExitShadowRead } from "@/lib/types";

export const dynamic = "force-dynamic";

/**
 * Read-only proxy for the backend SHADOW exit assessment. It only forwards the persisted
 * record (the backend never recomputes on GET); when the backend is unreachable no fixture or
 * estimated quantity is substituted.
 */
export async function GET() {
  const res = await fetchBackendJson<ExitShadowRead>("/api/metrics/exit-shadow", { timeoutMs: 3500 });
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
