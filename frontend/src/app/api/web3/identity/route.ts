import { NextResponse } from "next/server";
import { RECORDED_IDENTITY } from "@/lib/fixtures";
import { fetchBackendJson } from "@/lib/server-backend";
import type { Identity } from "@/lib/types";
import { identityFromProof, readRegisteredIdentity } from "@/lib/server-fuji-identity";

export const dynamic = "force-dynamic";

export async function GET() {
  try {
    const proof = await readRegisteredIdentity();
    if (proof) return NextResponse.json(identityFromProof(proof), { headers: { "X-AEGIS-Backend-Status": "LIVE", "X-AEGIS-Identity-Source": "FUJI_RPC" } });
  } catch {
    return NextResponse.json({ ...RECORDED_IDENTITY, verified: false, verification_status: "UNAVAILABLE" }, { headers: { "X-AEGIS-Identity-Source": "FUJI_RPC_UNAVAILABLE" } });
  }
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
