import { NextResponse } from "next/server";

export const dynamic = "force-dynamic";

function isVerifiedPublicHttpsOrigin(origin: string | undefined): origin is string {
  if (!origin) return false;
  try {
    const parsed = new URL(origin);
    if (parsed.protocol !== "https:") return false;
    const host = parsed.hostname.toLowerCase();
    if (
      host === "localhost" ||
      host === "127.0.0.1" ||
      host === "0.0.0.0" ||
      host.endsWith(".local") ||
      host.startsWith("192.168.") ||
      host.startsWith("10.")
    ) {
      return false;
    }
    return true;
  } catch {
    return false;
  }
}

export function buildErc8004RegistrationJson() {
  const configuredOrigin = process.env.AEGIS_PUBLIC_ORIGIN?.trim();
  const hasPublicHttps = isVerifiedPublicHttpsOrigin(configuredOrigin);
  const cleanOrigin = hasPublicHttps ? configuredOrigin.replace(/\/+$/, "") : null;

  const services = cleanOrigin
    ? [
        {
          name: "aegis-service-metadata",
          endpoint: `${cleanOrigin}/api/v1/service`,
          version: "1.0.0",
        },
        {
          name: "aegis-pretrade-risk-evaluate",
          endpoint: `${cleanOrigin}/api/v1/risk/evaluate`,
          version: "1.0.0",
        },
      ]
    : [];

  return {
    type: "https://eips.ethereum.org/EIPS/eip-8004#registration-v1",
    name: "AEGIS",
    description:
      "AEGIS — Autonomous Pre-Trade Risk-Checking & Self-Monitoring Trading Agent. Registered as an ERC-8004 agent identity on Avalanche Fuji (43113); Python risk engine, official OKX Agent Trade Kit (ATK) observations, LAYA operational classifier (CONTINUE/REVIEW/HALT), and EVREN bounded reasoning execute OFF-CHAIN. Live order execution is disabled.",
    image: null,
    services,
    endpoints: services,
    x402Support: false,
    active: true,
    registrations: [],
    supportedTrust: ["reputation"],
    aegisMetadata: {
      chainId: 43113,
      network: "avalanche-fuji",
      officialIdentityRegistry: "0x8004A818BFB912233c491871b3d84c89A494BD9e",
      officialReputationRegistry: "0x8004B663056A597Dffe9eCcC1965A193B7388713",
      offChainRuntime: true,
      onChainInference: false,
      liveExecutionEnabled: false,
      orderPermissionDelegation: false,
      okxAiListingStatus: "NOT_LISTED",
      okxAiIntegrationFeasibility: "POSSIBLE",
      publicOriginStatus: hasPublicHttps ? "HTTPS_CONFIGURED" : "PUBLIC_NOT_VERIFIED",
      publicOrigin: cleanOrigin,
      note: hasPublicHttps
        ? "Public HTTPS services listed for read-only service descriptor and X-AEGIS-Key protected pre-trade risk assessment. Private execution/control endpoints are never exposed publicly."
        : "Services array is intentionally empty until a verified public HTTPS origin (AEGIS_PUBLIC_ORIGIN) is live. Loopback/localhost or LAN IP never masquerades as a public service.",
    },
  };
}

export async function GET() {
  return NextResponse.json(buildErc8004RegistrationJson());
}
