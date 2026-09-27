import { describe, expect, it } from "vitest";
import { computeLivePortfolio } from "./portfolio";
import { portfolio, tick } from "@/test/mocks";

describe("computeLivePortfolio", () => {
  const base = portfolio({
    cash_balance: 5000,
    positions: [
      { ticker: "AAPL", quantity: 10, avg_cost: 100, current_price: 100, market_value: 1000, unrealized_pnl: 0, unrealized_pnl_percent: 0 },
      { ticker: "TSLA", quantity: 2.5, avg_cost: 200, current_price: 190, market_value: 475, unrealized_pnl: -25, unrealized_pnl_percent: -5 },
    ],
  });

  it("revalues positions from streamed prices", () => {
    const live = computeLivePortfolio(base, { ...tick("AAPL", 110), ...tick("TSLA", 220) });
    const [aapl, tsla] = live.positions;
    expect(aapl.market_value).toBeCloseTo(1100);
    expect(aapl.unrealized_pnl).toBeCloseTo(100);
    expect(aapl.unrealized_pnl_percent).toBeCloseTo(10);
    expect(tsla.market_value).toBeCloseTo(550);
    expect(tsla.unrealized_pnl).toBeCloseTo(50);
    expect(live.totalValue).toBeCloseTo(5000 + 1100 + 550);
    expect(live.totalPnl).toBeCloseTo(150);
    expect(live.cash).toBe(5000);
  });

  it("falls back to the server price when a ticker has no streamed price", () => {
    const live = computeLivePortfolio(base, tick("AAPL", 90));
    expect(live.positions[1].current_price).toBe(190);
    expect(live.totalValue).toBeCloseTo(5000 + 900 + 475);
    expect(live.totalPnl).toBeCloseTo(-100 - 25);
  });

  it("is all cash with no positions, and zero before load", () => {
    expect(computeLivePortfolio(portfolio(), {}).totalValue).toBe(10000);
    expect(computeLivePortfolio(null, {})).toEqual({ cash: 0, totalValue: 0, totalPnl: 0, positions: [] });
  });
});
