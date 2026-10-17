import { createHash } from "node:crypto";

export function verifyMetadataBytes(raw: Uint8Array, expectedSha256: string) {
  if (raw.byteLength > 16_384 || createHash("sha256").update(raw).digest("hex") !== expectedSha256) throw new Error("Published metadata digest mismatch.");
  const metadata = JSON.parse(Buffer.from(raw).toString("utf8"));
  if (metadata.type !== "https://eips.ethereum.org/EIPS/eip-8004#registration-v1" || metadata.name !== "AEGIS" || typeof metadata.description !== "string" || !metadata.description.includes("off-chain") || !Array.isArray(metadata.services) || !Array.isArray(metadata.registrations) || metadata.x402Support !== false) throw new Error("Published metadata schema invalid.");
  return metadata;
}
