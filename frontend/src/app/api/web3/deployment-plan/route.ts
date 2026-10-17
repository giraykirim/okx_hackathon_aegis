import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { NextResponse } from "next/server";
import { buildFujiPlan } from "@/lib/fuji-plan";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Public, unsigned data only. This route never loads a wallet or sends a transaction.
export async function GET() {
  try {
    const root = resolve(process.cwd(), "..");
    const [artifact, canonicalBytes, evidence] = await Promise.all([
      readFile(resolve(root, "web3/artifacts/RiskDecisionRegistry.json"), "utf8"),
      readFile(resolve(root, "web3/artifacts/receipt-assessment.json")),
      readFile(resolve(root, "backend/evidence/amendment-http.json"), "utf8"),
    ]);
    const recorded = JSON.parse(evidence).checks.excess_notional.response;
    return NextResponse.json(buildFujiPlan(JSON.parse(artifact), canonicalBytes, recorded), { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Verified compiled artifact or recorded assessment unavailable; signing disabled." }, { status: 503 });
  }
}
