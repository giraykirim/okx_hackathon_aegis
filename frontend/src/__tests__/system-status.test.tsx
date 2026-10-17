// @vitest-environment jsdom
import React from "react";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { OverviewBottomPanels } from "../components/OverviewBottomPanels";

afterEach(cleanup);
const pass = { status: "PASS" as const, evidence: [], checked_at: "2026-10-17T13:00:00Z" };
describe("Truthful system readiness", () => {
  it("shows model abstention and never enables exchange from a historical capability", () => {
    render(<OverviewBottomPanels events={[]} capabilities={{LAYA:pass,EVREN:pass,ATK_DEMO_ORDER_SUBMISSION:pass}} backendLive sourceMode="MARKET_ONLY" layaAbstained executionEnabled={false} />);
    expect(screen.getByText("Connected · LAYA abstaining")).toBeTruthy();
    expect(screen.getByText("Read-only · Safe")).toBeTruthy();
    expect(screen.getByText("Awaiting measured cycle")).toBeTruthy();
    expect(screen.queryByText(/< [15] ms/)).toBeNull();
  });
  it("does not claim live model connections or a detected registry when offline", () => {
    render(<OverviewBottomPanels events={[]} capabilities={{LAYA:pass,EVREN:pass}} backendLive={false} />);
    expect(screen.queryByText("Live Connected")).toBeNull();
    expect(screen.getByText("Verification unavailable")).toBeTruthy();
  });
});
describe("Armed demo readiness", () => {
  it("turns models and exchange green only when this armed demo run verified them", () => {
    render(<OverviewBottomPanels events={[]} capabilities={{LAYA:pass,EVREN:pass,ATK_MARKET:pass,ATK_DEMO_ORDER_SUBMISSION:pass}} backendLive sourceMode="OKX_DEMO" layaAbstained executionEnabled />);
    expect(screen.getByText("Demo order verified")).toBeTruthy();
    expect(screen.getByText("Last ATK read verified")).toBeTruthy();
    expect(screen.getByText("Connected · LAYA abstaining").className).toContain("4EE1C2");
  });
  it("shows awaiting rather than unavailable before the first cycle", () => {
    render(<OverviewBottomPanels events={[]} capabilities={{}} backendLive sourceMode="OKX_DEMO" executionEnabled />);
    expect(screen.getByText("Awaiting first cycle")).toBeTruthy();
    expect(screen.getByText("Demo configured · Policy gated")).toBeTruthy();
  });
});
