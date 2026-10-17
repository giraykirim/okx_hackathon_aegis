import { NextResponse } from "next/server";
import { RECORDED_SNAPSHOT_MARKET_ONLY } from "@/lib/fixtures";
import { fetchBackendJson } from "@/lib/server-backend";
import type { Snapshot } from "@/lib/types";
import { readUiIntegrations } from "@/lib/server-capabilities";

export const dynamic = "force-dynamic";

export async function GET() {
  const res = await fetchBackendJson<Snapshot>("/api/snapshot", { timeoutMs: 4000 });
  if (res.ok && res.data) {
    const integrations = await readUiIntegrations();
    return NextResponse.json({ ...res.data, capabilities: { ...res.data.capabilities, ...integrations.capabilities }, identity: integrations.identity ?? res.data.identity }, {
      headers: {
        "X-AEGIS-Backend-Status": "LIVE",
      },
    });
  }
  return NextResponse.json(RECORDED_SNAPSHOT_MARKET_ONLY, {
    headers: {
      "X-AEGIS-Backend-Status": "OFFLINE_FIXTURE",
      "X-AEGIS-Backend-Error": res.error || "unreachable",
    },
  });
}
