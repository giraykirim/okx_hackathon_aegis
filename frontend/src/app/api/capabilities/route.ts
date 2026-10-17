import { NextResponse } from "next/server";
import { RECORDED_SNAPSHOT_MARKET_ONLY } from "@/lib/fixtures";
import { fetchBackendJson } from "@/lib/server-backend";
import type { Capability } from "@/lib/types";
import { readUiIntegrations } from "@/lib/server-capabilities";

export const dynamic = "force-dynamic";

export async function GET() {
  const res = await fetchBackendJson<Record<string, Capability>>("/api/capabilities", {
    timeoutMs: 3500,
  });
  if (res.ok && res.data) {
    const integrations = await readUiIntegrations();
    return NextResponse.json({ ...res.data, ...integrations.capabilities }, {
      headers: {
        "X-AEGIS-Backend-Status": "LIVE",
      },
    });
  }
  return NextResponse.json(RECORDED_SNAPSHOT_MARKET_ONLY.capabilities, {
    headers: {
      "X-AEGIS-Backend-Status": "OFFLINE_FIXTURE",
      "X-AEGIS-Backend-Error": res.error || "unreachable",
    },
  });
}
