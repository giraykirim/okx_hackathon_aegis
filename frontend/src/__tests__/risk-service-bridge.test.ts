import { afterEach, describe, expect, it, vi } from "vitest";
import { POST } from "../app/api/v1/risk/evaluate/route";
import { fetchBackendJson, isAdminAuthorized } from "../lib/server-backend";

vi.mock("../lib/server-backend", () => ({ fetchBackendJson: vi.fn(), isAdminAuthorized: vi.fn() }));
afterEach(() => { vi.resetAllMocks(); vi.unstubAllEnvs(); });
describe("Authenticated risk-service bridge", () => {
  it.each([null, [], "text"].map(body => ({body})))("rejects a non-object request without a provider call: $body", async ({body}) => {
    const result = await POST(new Request("http://localhost/api/v1/risk/evaluate", {method:"POST",body:JSON.stringify(body)}));
    expect(result.status).toBe(400);
    expect(fetchBackendJson).not.toHaveBeenCalled();
  });
  it("allows the bounded backend analysis deadline and forwards only server credentials", async () => {
    vi.stubEnv("AEGIS_SERVICE_API_KEY", "unit-service-key");
    vi.mocked(isAdminAuthorized).mockReturnValue({authorized:true,statusCode:200});
    vi.mocked(fetchBackendJson).mockResolvedValue({ok:true,status:200,data:{request_id:"unit",execution_authorized:false}});
    const result=await POST(new Request("http://localhost/api/v1/risk/evaluate", {method:"POST",body:JSON.stringify({request_id:"unit",symbol:"BTC-USDT",proposed_action:"BUY",proposed_notional:"10"})}));
    expect(result.headers.get("X-AEGIS-Backend-Status")).toBe("LIVE");
    expect(vi.mocked(fetchBackendJson).mock.calls[0][1]?.timeoutMs).toBeGreaterThanOrEqual(35_000);
  });
  it("never calls the protected service for a view-only caller", async () => {
    vi.stubEnv("AEGIS_SERVICE_API_KEY", "unit-service-key");
    vi.mocked(isAdminAuthorized).mockReturnValue({authorized:false,statusCode:401});
    const result=await POST(new Request("http://localhost/api/v1/risk/evaluate", {method:"POST",body:JSON.stringify({proposed_notional:"10"})}));
    expect(fetchBackendJson).not.toHaveBeenCalled();
    expect(result.headers.get("X-AEGIS-Backend-Status")).toBe("RECORDED_PROOF");
  });
});
