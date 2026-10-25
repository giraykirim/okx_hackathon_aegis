// @vitest-environment jsdom
import React from "react";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import { NextRequest } from "next/server";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import DashboardPage from "../app/page";
import * as exitRoute from "../app/api/metrics/exit-shadow/route";
import * as snapshotRoute from "../app/api/snapshot/route";
import type { ExitProposal, ExitShadowRead } from "../lib/types";
// The exact backend `/api/metrics/exit-shadow` contract: backend/tests/test_exit_shadow.py
// compares a real agent-cycle API response against this file (shape and values).
import CURRENT_JSON from "./fixtures/exit-shadow-current.json";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  usePathname: () => "/",
  useSearchParams: () => new URLSearchParams(),
}));

const CURRENT = CURRENT_JSON as ExitShadowRead;

function variant(read: Partial<ExitShadowRead>, proposal: Partial<ExitProposal> = {}): ExitShadowRead {
  const assessment = CURRENT.assessment!;
  return {
    ...CURRENT,
    ...read,
    assessment: read.assessment === null ? null : { ...assessment, proposal: { ...assessment.proposal, ...proposal } },
  };
}

const ROUTES: Record<string, (req: NextRequest) => Promise<Response>> = {
  "/api/snapshot": snapshotRoute.GET as never,
  "/api/metrics/exit-shadow": exitRoute.GET as never,
};

/** Browser-side network state: `offline` rejects like a dropped connection, `hang` never answers. */
interface BrowserNet {
  offline: boolean;
  hang: boolean;
  rejectPaths: string[];
  rejected: number;
}

/** Browser fetch -> the real Next route handler -> mocked backend (127.0.0.1:8000). */
function installFetch(
  backend: Record<string, unknown>,
  net: BrowserNet = { offline: false, hang: false, rejectPaths: [], rejected: 0 }
) {
  const backendCalls: string[] = [];
  vi.stubGlobal("fetch", async (input: string | URL, init?: RequestInit) => {
    const url = String(input);
    if (url.startsWith("http://127.0.0.1:8000")) {
      const path = new URL(url).pathname;
      backendCalls.push(`${init?.method ?? "GET"} ${path}`);
      if (!(path in backend)) return new Response("down", { status: 503 });
      return new Response(JSON.stringify(backend[path]), { status: 200 });
    }
    const local = new URL(url, "http://localhost");
    if (net.hang) return new Promise<Response>(() => {});
    if (net.offline || net.rejectPaths.includes(local.pathname)) {
      net.rejected++;
      throw new TypeError("Failed to fetch");
    }
    const handler = ROUTES[local.pathname];
    if (!handler) return new Response("not found", { status: 404 });
    return handler(new NextRequest(local));
  });
  return backendCalls;
}

/** Fire the dashboard's real 6s polling interval (and the panel clock) without waiting 6s. */
async function poll(ms = 6100) {
  await act(async () => {
    await vi.advanceTimersByTimeAsync(ms);
  });
}

function capacityShown(region: HTMLElement) {
  return within(region).queryAllByText("0.00019980 BTC").length === 2;
}

async function panel() {
  await screen.findByText("LIVE /api/metrics/exit-shadow");
  return screen.getByRole("region", { name: "Shadow exit assessment" });
}

beforeEach(() => vi.unstubAllGlobals());
afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.useRealTimers();
});

describe("Dashboard shadow exit flow (page -> Next proxy -> backend record)", () => {
  it("renders the current persisted assessment with SHADOW status and no order path", async () => {
    const calls = installFetch({ "/api/metrics/exit-shadow": CURRENT });
    render(<DashboardPage />);
    const region = await panel();
    const view = within(region);
    expect(view.getByTestId("exit-shadow-banner").textContent).toBe("SHADOW — emir gönderilmez · no order is sent");
    expect(view.getByTestId("exit-shadow-status").textContent).toBe("PROPOSE_CLOSE");
    expect(view.getAllByText("0.00019980 BTC")).toHaveLength(2); // owned net and close capacity
    expect(view.getByText("0.00000000 BTC")).toBeTruthy();
    expect(view.getByText("0.00000001 / 0.00001")).toBeTruthy();
    expect(view.getByTestId("exit-shadow-freshness").textContent).toContain(
      "Current · assessed 2026-10-25T12:00:00+00:00 (age 3s, max 60s) · OKX_DEMO"
    );
    expect(view.getByTestId("exit-shadow-reasons").textContent).toBe("Blocking reasons: none");
    expect(region.textContent).toContain("not a sell signal");
    // Only reads reached the backend for this panel; nothing was posted.
    expect(calls.filter((c) => c.endsWith("/api/metrics/exit-shadow"))).not.toHaveLength(0);
    expect(calls.every((c) => c.startsWith("GET "))).toBe(true);
  });

  it("shows no assessment and no quantity when the backend is unreachable", async () => {
    installFetch({});
    render(<DashboardPage />);
    expect(await screen.findByText("Backend unavailable · no exit assessment shown")).toBeTruthy();
    const region = screen.getByRole("region", { name: "Shadow exit assessment" });
    expect(region.textContent).not.toMatch(/BTC|PROPOSE|NO_EXIT|REVIEW/);
  });

  it("distinguishes 'no assessment yet' from an outage and from a verified zero inventory", async () => {
    installFetch({
      "/api/metrics/exit-shadow": variant({ state: "NO_ASSESSMENT", current: false, age_seconds: null, assessment: null }),
    });
    render(<DashboardPage />);
    const region = await panel();
    expect(within(region).getByText("No shadow exit assessment recorded yet.")).toBeTruthy();
    expect(region.textContent).not.toMatch(/BTC/);
    cleanup();

    installFetch({
      "/api/metrics/exit-shadow": variant({}, {
        status: "NO_EXIT", reasons: ["no_owned_inventory"], owned_net_btc: "0.00000000",
        sellable_btc: null, proposed_sell_btc: null, remaining_btc: null, lot_size: null, min_size: null,
      }),
    });
    render(<DashboardPage />);
    const zero = within(await panel());
    expect(zero.getByTestId("exit-shadow-status").textContent).toBe("NO_EXIT");
    expect(zero.getByTestId("exit-shadow-zero").textContent).toContain("Verified zero owned inventory");
    expect(zero.getByText("0.00000000 BTC")).toBeTruthy();
  });

  it("never presents a stale or superseded record as a current quantity", async () => {
    for (const state of ["STALE", "SUPERSEDED"] as const) {
      installFetch({
        "/api/metrics/exit-shadow": variant({
          state,
          current: false,
          age_seconds: 3600,
          not_current_reasons: state === "STALE" ? ["assessment_stale"] : ["inventory_changed_since_assessment"],
        }),
      });
      render(<DashboardPage />);
      const region = await panel();
      const view = within(region);
      expect(view.getByTestId("exit-shadow-status").textContent).toBe("Last recorded PROPOSE_CLOSE (not current)");
      expect(view.getByTestId("exit-shadow-withheld")).toBeTruthy();
      expect(view.getByTestId("exit-shadow-freshness").textContent).toContain(
        state === "STALE" ? "STALE — not current" : "SUPERSEDED"
      );
      expect(region.textContent).not.toMatch(/\d\.\d+ BTC/);
      cleanup();
    }
  });

  it("shows REVIEW blocking reasons without inventing a quantity", async () => {
    installFetch({
      "/api/metrics/exit-shadow": variant({}, {
        status: "REVIEW", reasons: ["unresolved_prior_order"], owned_net_btc: "0.00019980",
        sellable_btc: null, proposed_sell_btc: null, remaining_btc: null, lot_size: null, min_size: null,
      }),
    });
    render(<DashboardPage />);
    const view = within(await panel());
    expect(view.getByTestId("exit-shadow-status").textContent).toBe("REVIEW");
    expect(view.getByTestId("exit-shadow-reasons").textContent).toBe("Blocking reasons: unresolved_prior_order");
    expect(view.getAllByText("unavailable").length).toBeGreaterThanOrEqual(3);
  });

  it("browser connection loss: first read -> rejected polls withhold capacity -> reconnect restores it", async () => {
    // Fake only intervals and the clock; promises, React scheduling and waitFor stay real.
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"] });
    const net: BrowserNet = { offline: false, hang: false, rejectPaths: [], rejected: 0 };
    installFetch({ "/api/metrics/exit-shadow": CURRENT }, net);
    render(<DashboardPage />);
    const region = await panel();
    expect(capacityShown(region)).toBe(true);

    net.offline = true;
    await poll();
    await waitFor(() =>
      expect(screen.getByTestId("exit-shadow-source").textContent).toBe("Connection lost · no exit assessment shown")
    );
    expect(net.rejected).toBeGreaterThan(0);
    expect(region.textContent).not.toMatch(/\d\.\d+ BTC|PROPOSE_CLOSE|LIVE \/api\/metrics\/exit-shadow/);

    net.offline = false;
    await poll();
    await waitFor(() => expect(capacityShown(region)).toBe(true));
    expect(within(region).getByTestId("exit-shadow-status").textContent).toBe("PROPOSE_CLOSE");
  });

  it("backend 503 after a good read is reported apart from a browser-side rejection", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"] });
    const backend: Record<string, unknown> = { "/api/metrics/exit-shadow": CURRENT };
    installFetch(backend);
    render(<DashboardPage />);
    const region = await panel();
    expect(capacityShown(region)).toBe(true);

    delete backend["/api/metrics/exit-shadow"]; // the browser reaches Next; the backend answers 503
    await poll();
    await waitFor(() =>
      expect(screen.getByTestId("exit-shadow-source").textContent).toBe("Backend unavailable · no exit assessment shown")
    );
    expect(region.textContent).not.toMatch(/\d\.\d+ BTC|PROPOSE_CLOSE/);
  });

  it("a malformed shadow response withholds capacity instead of keeping the previous one", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"] });
    const backend: Record<string, unknown> = { "/api/metrics/exit-shadow": CURRENT };
    installFetch(backend);
    render(<DashboardPage />);
    const region = await panel();
    expect(capacityShown(region)).toBe(true);

    backend["/api/metrics/exit-shadow"] = { unexpected: "shape" };
    await poll();
    await waitFor(() =>
      expect(screen.getByTestId("exit-shadow-source").textContent).toBe("Backend unavailable · no exit assessment shown")
    );
    expect(region.textContent).not.toMatch(/\d\.\d+ BTC|PROPOSE_CLOSE/);
  });

  it("an unrelated endpoint failure does not block a successful shadow read", async () => {
    installFetch({ "/api/metrics/exit-shadow": CURRENT }, {
      offline: false, hang: false, rejectPaths: ["/api/snapshot", "/api/events"], rejected: 0,
    });
    render(<DashboardPage />);
    const region = await panel();
    expect(capacityShown(region)).toBe(true);
  });

  it("with no new response the last record keeps ageing and its capacity expires", async () => {
    vi.useFakeTimers({ toFake: ["setInterval", "clearInterval", "Date"] });
    const net: BrowserNet = { offline: false, hang: false, rejectPaths: [], rejected: 0 };
    installFetch({ "/api/metrics/exit-shadow": CURRENT }, net);
    render(<DashboardPage />);
    const region = await panel();
    expect(capacityShown(region)).toBe(true);

    net.hang = true; // polls are sent but never answered: no error, no new data
    await poll(5000); // market basis 3.001s + 5s: still inside its 15s bound
    expect(capacityShown(region)).toBe(true);
    await poll(8000); // 3.001s + 13s > 15s
    await waitFor(() => expect(capacityShown(region)).toBe(false));
    const view = within(region);
    expect(view.getByTestId("exit-shadow-status").textContent).toBe("Last recorded PROPOSE_CLOSE (not current)");
    expect(view.getByTestId("exit-shadow-freshness").textContent).toContain("market_data_expired");
    expect(view.getByTestId("exit-shadow-freshness").textContent).toContain("age 16s");
    expect(region.textContent).not.toMatch(/\d\.\d+ BTC/);
  });

  it("proxy forwards one backend read per request and adds no fixture when offline", async () => {
    const calls = installFetch({ "/api/metrics/exit-shadow": CURRENT });
    const live = await exitRoute.GET();
    expect(live.headers.get("X-AEGIS-Backend-Status")).toBe("LIVE");
    expect(await live.json()).toEqual(CURRENT);
    expect(calls).toEqual(["GET /api/metrics/exit-shadow"]);

    installFetch({});
    const down = await exitRoute.GET();
    expect(down.status).toBe(503);
    expect(await down.json()).toBeNull();
  });
});
