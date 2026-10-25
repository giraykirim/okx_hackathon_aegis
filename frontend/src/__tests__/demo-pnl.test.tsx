// @vitest-environment jsdom
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { EventTimelineAndCapabilities } from "../components/EventTimelineAndCapabilities";
import type { Metrics } from "../lib/types";

afterEach(cleanup);

const BASE: Metrics = {
  decisions: 3,
  vetoed: 1,
  verified_exchange_orders: 2,
  mock_executions: 0,
  unresolved_orders: 0,
  pnl: null,
};

// Component-level test only: EventTimelineAndCapabilities is not rendered by the home page.
// The real page -> proxy -> backend flow is covered by dashboard-pnl-flow.test.tsx.
describe("Demo PnL card", () => {
  it("shows venue-derived net PnL while keeping account-level pnl unasserted", () => {
    render(
      <EventTimelineAndCapabilities
        events={[]}
        capabilities={{}}
        metrics={{
          ...BASE,
          demo_pnl: {
            schema_version: "aegis-demo-pnl-2",
            realized: "0.00000000",
            unrealized: "995.00000000",
            fees: "4.00000000",
            fee_breakdown: { BTC: "-0.00010000" },
            net: "995.00000000",
            inventory_qty: "0.09990000",
            cost_basis: "4000.00000000",
            average_cost: "40040.04004004",
            mark_price: "50000.00000000",
            mark: null,
            valuation_status: "CURRENT_MARK",
            fill_count: 1,
            unmatched_sell_qty: "0.00000000",
            complete: true,
            issues: [],
            warnings: [],
            ledger: [],
            excluded_unowned_fills: 0,
            method: "average-cost",
            as_of: "2026-10-21T12:04:19.035167Z",
          },
        }}
      />
    );
    expect(screen.getByText("995.00000000 USDT")).toBeTruthy();
    expect(
      screen.getByText("realized 0.00000000 · fees 4.00000000")
    ).toBeTruthy();
    expect(screen.queryByText("null (NOT_TESTED)")).toBeNull();
  });

  it("stays empty until verified fills exist", () => {
    render(
      <EventTimelineAndCapabilities events={[]} capabilities={{}} metrics={BASE} />
    );
    expect(screen.getByText("awaiting verified fills")).toBeTruthy();
    expect(screen.queryByText(/USDT/)).toBeNull();
  });
});
