// @vitest-environment jsdom
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "../app/page";
import * as costRoute from "../app/api/metrics/cost-gate/route";
import * as decisionsRoute from "../app/api/decisions/route";
import * as eventsRoute from "../app/api/events/route";
import * as pnlRoute from "../app/api/metrics/pnl/route";
import * as metricsRoute from "../app/api/metrics/route";
import * as snapshotRoute from "../app/api/snapshot/route";
import type { CostGateSummary, DemoPnl } from "../lib/types";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

// Shape produced by backend `/api/metrics/pnl` for 0.1 BTC bought at 40000 with a
// -0.0001 BTC fee and a 50000 venue mark (synthetic example B).
const BACKEND_PNL: DemoPnl = {
  schema_version: "aegis-demo-pnl-2",
  realized: "0.00000000",
  unrealized: "995.00000000",
  net: "995.00000000",
  fees: "4.00000000",
  fee_breakdown: { BTC: "-0.00010000" },
  inventory_qty: "0.09990000",
  cost_basis: "4000.00000000",
  average_cost: "40040.04004004",
  fill_count: 1,
  unmatched_sell_qty: "0.00000000",
  complete: true,
  issues: [],
  warnings: [],
  ledger: [],
  mark_price: "50000.00000000",
  mark: {
    symbol: "BTC-USDT",
    price: "50000",
    bid: "49999",
    ask: "50001",
    observed_at: "2026-10-21T12:00:00+00:00",
    source: "OKX ticker last via official ATK",
    age_seconds: 3,
    stale: false,
    max_age_seconds: 60,
  },
  valuation_status: "CURRENT_MARK",
  excluded_unowned_fills: 0,
  method: "average-cost",
  as_of: "2026-10-21T12:00:03+00:00",
};

const BACKEND_COST: CostGateSummary = {
  schema_version: "aegis-cost-gate-1",
  evaluated_trade_proposals: 1,
  cost_approved: 0,
  blocked_when_enforced: 1,
  would_block_unenforced: 0,
  reason_counts: { cost_edge_source_missing: 1 },
  latest: {
    decision_id: "d",
    source_mode: "OKX_DEMO",
    timestamp: "2026-10-21T12:00:00+00:00",
    enforced: true,
    assessment: {
      status: "REVIEW",
      approved: false,
      reasons: ["cost_edge_source_missing"],
      explanation: "Blocked (cost_edge_source_missing); expected advantage cannot be measured.",
      inputs: {},
      breakdown: null,
    },
  },
};

const ROUTES: Record<string, (req: NextRequest) => Promise<Response>> = {
  "/api/snapshot": snapshotRoute.GET as never,
  "/api/events": eventsRoute.GET as never,
  "/api/metrics": metricsRoute.GET as never,
  "/api/decisions": decisionsRoute.GET as never,
  "/api/metrics/pnl": pnlRoute.GET as never,
  "/api/metrics/cost-gate": costRoute.GET as never,
};

/** Browser fetch -> the real Next route handler -> mocked backend (127.0.0.1:8000). */
function installFetch(backend: Record<string, unknown>) {
  const backendCalls: string[] = [];
  vi.stubGlobal("fetch", async (input: string | URL) => {
    const url = String(input);
    if (url.startsWith("http://127.0.0.1:8000")) {
      const path = new URL(url).pathname;
      backendCalls.push(path);
      if (!(path in backend)) return new Response("down", { status: 503 });
      return new Response(JSON.stringify(backend[path]), { status: 200 });
    }
    const local = new URL(url, "http://localhost");
    const handler = ROUTES[local.pathname];
    if (!handler) return new Response("not found", { status: 404 });
    return handler(new NextRequest(local));
  });
  return backendCalls;
}

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Dashboard PnL data flow (page -> Next proxy -> backend)", () => {
  it("renders backend PnL, mark provenance and cost-gate blocks on the real page", async () => {
    const calls = installFetch({
      "/api/metrics/pnl": BACKEND_PNL,
      "/api/metrics/cost-gate": BACKEND_COST,
    });
    render(<DashboardPage />);
    expect(await screen.findByText("LIVE /api/metrics/pnl")).toBeTruthy();
    expect(screen.getAllByText("995.00000000 USDT").length).toBeGreaterThan(0);
    expect(screen.getByText("0.09990000 BTC")).toBeTruthy();
    expect(screen.getByText("-0.00010000 BTC")).toBeTruthy();
    expect(screen.getByTestId("pnl-mark").textContent).toContain(
      "Current mark · 50000 from OKX ticker last via official ATK at 2026-10-21T12:00:00+00:00"
    );
    expect(screen.getByTestId("cost-gate").textContent).toContain("1 blocked");
    expect(calls).toContain("/api/metrics/pnl");
    expect(calls).toContain("/api/metrics/cost-gate");
  });

  it("shows no PnL figure when the backend is unreachable (no fixture substitution)", async () => {
    installFetch({});
    render(<DashboardPage />);
    expect(await screen.findByText("Backend unavailable · no PnL shown")).toBeTruthy();
    const panel = screen.getByRole("region", { name: "Demo PnL and cost gate" });
    expect(panel.textContent).not.toMatch(/USDT|Net|Realized/);
  });

  it("distinguishes 'no owned fills' (live null) from an outage", async () => {
    installFetch({ "/api/metrics/pnl": null, "/api/metrics/cost-gate": BACKEND_COST });
    render(<DashboardPage />);
    expect(await screen.findByText("No verified agent-owned fills recorded.")).toBeTruthy();
  });

  it("shows no accounting figure when the backend reports incomplete accounting", async () => {
    installFetch({
      "/api/metrics/pnl": {
        ...BACKEND_PNL,
        complete: false,
        net: null,
        realized: null,
        unrealized: null,
        fees: null,
        inventory_qty: null,
        cost_basis: null,
        average_cost: null,
        valuation_status: "ACCOUNTING_INCOMPLETE",
        issues: ["missing_fee:o1"],
      },
      "/api/metrics/cost-gate": BACKEND_COST,
    });
    render(<DashboardPage />);
    expect((await screen.findByTestId("pnl-issues")).textContent).toContain("missing_fee:o1");
    expect(screen.getByTestId("pnl-mark").textContent).toContain("Accounting incomplete");
    const panel = screen.getByRole("region", { name: "Demo PnL and cost gate" });
    expect(panel.textContent).not.toMatch(/\d+\.\d+ (USDT|BTC)/);
  });
});
