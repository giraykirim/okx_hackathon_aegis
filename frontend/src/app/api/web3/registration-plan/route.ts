import { readFile } from "node:fs/promises";
import { resolve } from "node:path";
import { NextResponse } from "next/server";
import { createPublicClient, http } from "viem";
import { avalancheFuji } from "viem/chains";
import { AGENT_METADATA_URI, IDENTITY_ABI, IDENTITY_REGISTRY, verifyRegistration, type RegistrationProof } from "@/lib/fuji-identity";
import { verifyMetadataBytes } from "@/lib/fuji-identity-metadata";
import { EXPECTED_FUJI_ACCOUNT, FUJI_RPC } from "@/lib/fuji-wallet";

export const dynamic = "force-dynamic";
export const runtime = "nodejs";

// Only fixed public metadata/chain reads. No key is loaded and no mint is sent.
export async function GET() {
  try {
    const root = resolve(process.cwd(), "../web3");
    const publication = JSON.parse(await readFile(resolve(root, "metadata-publication.json"), "utf8"));
    if (publication.agent_uri !== AGENT_METADATA_URI) throw new Error("Unexpected metadata destination");
    const response = await fetch(AGENT_METADATA_URI, { cache: "no-store", redirect: "error", signal: AbortSignal.timeout(8000), headers: { Accept: "application/json" } });
    if (!response.ok || !response.body) throw new Error("Public metadata unavailable");
    const reader = response.body.getReader();
    const chunks: Uint8Array[] = []; let size = 0;
    try {
      while (true) {
        const { done, value } = await reader.read(); if (done) break;
        size += value.byteLength; if (size > 16_384) throw new Error("Metadata size limit");
        chunks.push(value);
      }
    } finally { await reader.cancel(); }
    verifyMetadataBytes(Buffer.concat(chunks), publication.content_sha256);
    const client = createPublicClient({ chain: avalancheFuji, transport: http(process.env.FUJI_RPC_URL || FUJI_RPC, { timeout: 8000, retryCount: 0 }) });
    if (await client.getChainId() !== 43113) throw new Error("Wrong chain");
    const [code, owned] = await Promise.all([
      client.getCode({ address: IDENTITY_REGISTRY }),
      client.readContract({ address: IDENTITY_REGISTRY, abi: IDENTITY_ABI, functionName: "balanceOf", args: [EXPECTED_FUJI_ACCOUNT] }),
    ]);
    if (!code || code === "0x") throw new Error("Registry unavailable");
    let registered: RegistrationProof | null = null;
    const previous = JSON.parse(await readFile(resolve(root, "registration-proof.json"), "utf8").catch(() => "null"));
    if (previous?.verified && /^0x[\da-f]{64}$/i.test(previous.registrationTxHash ?? "")) registered = await verifyRegistration(client, previous.registrationTxHash);
    return NextResponse.json({ chain_id: 43113, expected_account: EXPECTED_FUJI_ACCOUNT, registry_address: IDENTITY_REGISTRY, agent_uri: AGENT_METADATA_URI, metadata_sha256: publication.content_sha256, metadata_verified: true, owned_identity_count: owned.toString(), registered }, { headers: { "Cache-Control": "no-store" } });
  } catch {
    return NextResponse.json({ error: "Public metadata or Fuji preflight unavailable; identity signing disabled." }, { status: 503 });
  }
}
