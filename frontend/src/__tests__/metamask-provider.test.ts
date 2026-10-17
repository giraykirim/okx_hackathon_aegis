// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { discoverMetaMask } from "../lib/metamask-provider";

describe("Multiple installed wallet discovery", () => {
  it("selects the announced MetaMask provider rather than another wallet claiming isMetaMask", () => {
    const other = { isMetaMask: true, request: vi.fn() };
    const metamask = { request: vi.fn() };
    const announce = () => {
      window.dispatchEvent(new CustomEvent("eip6963:announceProvider", { detail: { info: { rdns: "com.binance.wallet" }, provider: other } }));
      window.dispatchEvent(new CustomEvent("eip6963:announceProvider", { detail: { info: { rdns: "io.metamask" }, provider: metamask } }));
    };
    window.addEventListener("eip6963:requestProvider", announce);
    const discovery = discoverMetaMask(window);
    expect(discovery.get()).toBe(metamask);
    expect(other.request).not.toHaveBeenCalled();
    discovery.stop(); window.removeEventListener("eip6963:requestProvider", announce);
  });
  it("does not fall back to an unidentified provider", () => {
    const discovery = discoverMetaMask(window);
    window.dispatchEvent(new CustomEvent("eip6963:announceProvider", { detail: { info: { rdns: "com.binance.wallet" }, provider: { isMetaMask: true, request: vi.fn() } } }));
    expect(discovery.get()).toBeUndefined();
    discovery.stop();
  });
});
