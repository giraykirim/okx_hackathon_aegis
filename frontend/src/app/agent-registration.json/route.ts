import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { NextResponse } from "next/server";
import { AGENT_METADATA_URI } from "@/lib/fuji-identity";
import { verifyMetadataBytes } from "@/lib/fuji-identity-metadata";

export const dynamic = "force-dynamic";

// Serve the reviewed, actually published descriptor; an env hostname is not a
// verified service deployment and must never silently advertise an API.
export function buildErc8004RegistrationJson() {
  const root = resolve(process.cwd(), "../web3");
  const publication = JSON.parse(readFileSync(resolve(root, "metadata-publication.json"), "utf8"));
  if (publication.agent_uri !== AGENT_METADATA_URI || publication.http_status !== 200) throw new Error("Published metadata not verified");
  return verifyMetadataBytes(readFileSync(resolve(root, "public/agent-registration.json")), publication.content_sha256);
}

export async function GET() {
  try {
    return NextResponse.json(buildErc8004RegistrationJson());
  } catch {
    return NextResponse.json({ error: "Reviewed public descriptor unavailable" }, { status: 503 });
  }
}
