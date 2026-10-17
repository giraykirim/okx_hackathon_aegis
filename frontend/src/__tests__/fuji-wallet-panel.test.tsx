// @vitest-environment jsdom
import React from "react";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { FujiWalletPanel } from "../components/FujiWalletPanel";

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe("Fuji wallet panel", () => {
  it("does not request wallet access or sign on mount", async () => {
    const request = vi.fn();
    Object.defineProperty(window, "ethereum", { value: { isMetaMask: true, request }, configurable: true });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    render(<FujiWalletPanel onVerified={() => {}} />);
    expect(await screen.findByText(/signing disabled/i)).toBeTruthy();
    expect(request).not.toHaveBeenCalled();
    expect((screen.getByRole("button", { name: /deploy receipt contract/i }) as HTMLButtonElement).disabled).toBe(true);
  });
  it("explains that a MetaMask browser is needed when no extension is injected", async () => {
    Object.defineProperty(window, "ethereum", { value: undefined, configurable: true });
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue({ ok: false }));
    render(<FujiWalletPanel onVerified={() => {}} />);
    fireEvent.click(screen.getByRole("button", { name: /connect metamask/i }));
    expect(await screen.findByText(/open this page in the browser/i)).toBeTruthy();
  });
});
