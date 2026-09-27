import { afterEach, describe, expect, it, vi } from "vitest";
import { api, ApiError } from "./api";
import { mockFetch } from "@/test/mocks";

afterEach(() => vi.unstubAllGlobals());

describe("api", () => {
  it("posts trades as JSON", async () => {
    const fetch = mockFetch({
      "POST /api/portfolio/trade": () => ({ body: { trade: { id: "1" }, portfolio: {} } }),
    });
    await api.trade("AAPL", "buy", 2.5);
    const [, init] = fetch.mock.calls[0];
    expect(JSON.parse(String(init?.body))).toEqual({ ticker: "AAPL", side: "buy", quantity: 2.5 });
  });

  it("surfaces the server's error message", async () => {
    mockFetch({ "POST /api/portfolio/trade": () => ({ status: 400, body: { error: "Insufficient cash" } }) });
    await expect(api.trade("AAPL", "buy", 1e9)).rejects.toEqual(new ApiError("Insufficient cash", 400));
  });

  it("handles 204 deletes and unwraps list responses", async () => {
    mockFetch({
      "DELETE /api/watchlist/AAPL": () => ({ status: 204 }),
      "GET /api/portfolio/trades": () => ({ body: { trades: [{ id: "t" }] } }),
    });
    await expect(api.removeWatchlist("AAPL")).resolves.toBeUndefined();
    await expect(api.getTrades()).resolves.toEqual([{ id: "t" }]);
  });
});
