import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { verifyMetadataBytes } from "../lib/fuji-identity-metadata";
import { buildErc8004RegistrationJson } from "../app/agent-registration.json/route";

const root = resolve(process.cwd(), "../web3");
const raw = readFileSync(resolve(root, "public/agent-registration.json"));
const publication = JSON.parse(readFileSync(resolve(root, "metadata-publication.json"), "utf8"));
describe("Published registration metadata preflight", () => {
  it("serves the published registration without advertising an unverified configured host", () => {
    const previous = process.env.AEGIS_PUBLIC_ORIGIN;
    process.env.AEGIS_PUBLIC_ORIGIN = "https://not-verified.example.invalid";
    try {
      const descriptor = buildErc8004RegistrationJson();
      expect(descriptor.registrations).toEqual(JSON.parse(raw.toString()).registrations);
      expect(descriptor.services).toEqual([]);
      expect(descriptor.active).toBe(false);
    } finally {
      if (previous === undefined) delete process.env.AEGIS_PUBLIC_ORIGIN;
      else process.env.AEGIS_PUBLIC_ORIGIN = previous;
    }
  });
  it("accepts the actual reviewed descriptor without inventing service availability", () => {
    const metadata = verifyMetadataBytes(raw, publication.content_sha256);
    expect(metadata.name).toBe("AEGIS");
    expect(metadata.services).toEqual([]); expect(metadata.active).toBe(false);
  });
  it("rejects modified external content even if it is valid JSON", () => {
    const modified = Buffer.from(raw.toString().replace('"name": "AEGIS"', '"name": "Changed"'));
    expect(() => verifyMetadataBytes(modified, publication.content_sha256)).toThrow(/digest/i);
  });
});
