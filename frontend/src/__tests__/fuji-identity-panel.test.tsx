// @vitest-environment jsdom
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FujiIdentityPanel } from "../components/FujiIdentityPanel";
import { AGENT_METADATA_URI } from "../lib/fuji-identity";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
describe("Explicit MetaMask identity registration", () => {
  it("disables minting if public metadata verification fails", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    render(<FujiIdentityPanel onRegistered={() => {}} />);
    expect(await screen.findByText(/metadata.*unavailable/i)).toBeTruthy();
    expect((screen.getByRole("button", { name: /register ERC-8004 identity/i }) as HTMLButtonElement).disabled).toBe(true);
  });
  it("never requests a signature on mount and blocks an already-owned identity", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: true, json: async () => ({ agent_uri: AGENT_METADATA_URI, metadata_verified: true, owned_identity_count: "1", registered: null }) }));
    render(<FujiIdentityPanel onRegistered={() => {}} />);
    expect(await screen.findByText(/existing identity.*mint/i)).toBeTruthy();
    expect((screen.getByRole("button", { name: /register ERC-8004 identity/i }) as HTMLButtonElement).disabled).toBe(true);
  });
});
