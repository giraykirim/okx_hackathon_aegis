import { NextResponse } from "next/server";
import { RECORDED_IDENTITY } from "@/lib/fixtures";
import { fetchBackendJson } from "@/lib/server-backend";
import type { Identity } from "@/lib/types";

export const dynamic = "force-dynamic";

export async function GET() {
  const res = await fetchBackendJson<Identity>("/api/web3/identity", { timeoutMs: 3500 });
  if (res.ok && res.data) {
    return NextResponse.json(res.data, {
      headers: {
        "X-AEGIS-Backend-Status": "LIVE",
      },
    });
  }
  return NextResponse.json(RECORDED_IDENTITY, {
    headers: {
      "X-AEGIS-Backend-Status": "OFFLINE_FIXTURE",
      "X-AEGIS-Backend-Error": res.error || "unreachable",
    },
  });
}
