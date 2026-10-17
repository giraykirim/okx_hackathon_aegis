import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import type { Capability, Identity } from "./types";
import { diagnosticCapabilities } from "./capability-evidence";
import { identityFromProof, readRegisteredIdentity } from "./server-fuji-identity";

let cached: { until: number; promise: Promise<{ capabilities: Record<string, Capability>; identity: Identity | null }> } | undefined;

// 30s deduplication avoids public RPC floods across Overview, Activity and raw status.
// checked_at remains the actual RPC/probe timestamp, never the cache lookup time.
export function readUiIntegrations() {
  if (cached && cached.until > Date.now()) return cached.promise;
  const promise = (async () => {
    let capabilities: Record<string, Capability> = {};
    try {
      const raw = await readFile(resolve(process.cwd(), "../backend/evidence/models.json"), "utf8");
      if (raw.length <= 256_000) capabilities = diagnosticCapabilities(JSON.parse(raw));
    } catch { /* No evidence is NOT_TESTED, not an optimistic PASS. */ }
    let identity: Identity | null = null;
    try {
      const proof = await readRegisteredIdentity();
      if (proof) {
        identity = identityFromProof(proof);
        capabilities.ERC8004 = { status: "PASS", checked_at: proof.checkedAt,
          evidence: [proof.registrationTxHash, `Fuji RPC: Registered event, ownerOf and tokenURI verified; agent=${proof.agentId}`] };
      }
    } catch {
      capabilities.ERC8004 = { status: "NOT_TESTED", checked_at: null, evidence: ["Fresh Fuji RPC verification unavailable"] };
    }
    return { capabilities, identity };
  })();
  cached = { until: Date.now() + 30_000, promise };
  return promise;
}
