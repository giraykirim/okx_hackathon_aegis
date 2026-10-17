import type { WalletProvider } from "./fuji-wallet";

// window.ethereum / isMetaMask are ambiguous with multiple installed wallets.
// Discover the specific wallet without requesting account access or signing.
export function discoverMetaMask(target: Window, onProvider?: (provider: WalletProvider) => void) {
  let provider: WalletProvider | undefined;
  const announce = (event: Event) => {
    const detail = (event as CustomEvent).detail;
    if (!detail || detail.info?.rdns !== "io.metamask" || typeof detail.provider?.request !== "function" || detail.provider === provider) return;
    provider = detail.provider;
    onProvider?.(detail.provider);
  };
  target.addEventListener("eip6963:announceProvider", announce);
  target.dispatchEvent(new Event("eip6963:requestProvider"));
  return { get: () => provider, stop: () => target.removeEventListener("eip6963:announceProvider", announce) };
}
