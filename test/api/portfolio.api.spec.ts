import { test, expect, DEFAULT_TICKERS } from "../fixtures";

test.describe("portfolio API", () => {
  test("health check", async ({ request }) => {
    const res = await request.get("/api/health");
    expect(res.status()).toBe(200);
    expect(await res.json()).toEqual({ status: "ok" });
  });

  test("reset returns the seed portfolio", async ({ request }) => {
    const res = await request.post("/api/portfolio/reset");
    expect(res.status()).toBe(200);
    const body = await res.json();
    expect(body.cash_balance).toBe(10000);
    expect(body.total_value).toBe(10000);
    expect(body.positions).toEqual([]);
  });

  test("GET /api/portfolio shape", async ({ request }) => {
    const body = await (await request.get("/api/portfolio")).json();
    expect(body).toMatchObject({ cash_balance: 10000, total_value: 10000, total_unrealized_pnl: 0, positions: [] });
  });

  test("buy fills at a cached price and updates cash and position", async ({ request }) => {
    const res = await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "buy", quantity: 2.5 } });
    expect(res.status(), await res.text()).toBe(200);
    const { trade, portfolio } = await res.json();
    expect(trade).toMatchObject({ ticker: "AAPL", side: "buy", quantity: 2.5 });
    expect(trade.id).toBeTruthy();
    expect(trade.executed_at).toMatch(/Z$/);
    expect(trade.price).toBeGreaterThan(0);
    expect(portfolio.cash_balance).toBeCloseTo(10000 - 2.5 * trade.price, 1) // API rounds money to cents;
    const pos = portfolio.positions.find((p: { ticker: string }) => p.ticker === "AAPL");
    expect(pos).toMatchObject({ ticker: "AAPL", quantity: 2.5 });
    expect(pos.avg_cost).toBeCloseTo(trade.price, 6);
    for (const key of ["current_price", "market_value", "unrealized_pnl", "unrealized_pnl_percent"]) {
      expect(typeof pos[key]).toBe("number");
    }
  });

  test("lowercase ticker is normalized", async ({ request }) => {
    const res = await request.post("/api/portfolio/trade", { data: { ticker: "aapl", side: "buy", quantity: 1 } });
    expect(res.status(), await res.text()).toBe(200);
    expect((await res.json()).trade.ticker).toBe("AAPL");
  });

  test("buys average cost; sells keep avg_cost; selling to zero deletes position", async ({ request }) => {
    const b1 = (await (await request.post("/api/portfolio/trade", { data: { ticker: "MSFT", side: "buy", quantity: 1 } })).json()).trade;
    const b2res = await request.post("/api/portfolio/trade", { data: { ticker: "MSFT", side: "buy", quantity: 3 } });
    const { trade: b2, portfolio: p2 } = await b2res.json();
    const pos2 = p2.positions.find((p: { ticker: string }) => p.ticker === "MSFT");
    expect(pos2.quantity).toBeCloseTo(4, 9);
    expect(pos2.avg_cost).toBeCloseTo((b1.price * 1 + b2.price * 3) / 4, 6);

    const s1 = await request.post("/api/portfolio/trade", { data: { ticker: "MSFT", side: "sell", quantity: 1.5 } });
    expect(s1.status(), await s1.text()).toBe(200);
    const pos3 = (await s1.json()).portfolio.positions.find((p: { ticker: string }) => p.ticker === "MSFT");
    expect(pos3.quantity).toBeCloseTo(2.5, 9);
    expect(pos3.avg_cost).toBeCloseTo(pos2.avg_cost, 9);

    const s2 = await request.post("/api/portfolio/trade", { data: { ticker: "MSFT", side: "sell", quantity: 2.5 } });
    expect(s2.status(), await s2.text()).toBe(200);
    const p4 = (await s2.json()).portfolio;
    expect(p4.positions.find((p: { ticker: string }) => p.ticker === "MSFT")).toBeUndefined();
  });

  test("fractional float residue counts as zero", async ({ request }) => {
    await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "buy", quantity: 0.1 } });
    await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "buy", quantity: 0.2 } });
    const res = await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "sell", quantity: 0.3 } });
    expect(res.status(), await res.text()).toBe(200);
    expect((await res.json()).portfolio.positions).toEqual([]);
  });

  test("trade history is newest first and honors limit", async ({ request }) => {
    for (const ticker of ["AAPL", "MSFT", "NVDA"]) {
      const r = await request.post("/api/portfolio/trade", { data: { ticker, side: "buy", quantity: 1 } });
      expect(r.status()).toBe(200);
    }
    const all = (await (await request.get("/api/portfolio/trades")).json()).trades;
    expect(all.map((t: { ticker: string }) => t.ticker)).toEqual(["NVDA", "MSFT", "AAPL"]);
    for (const t of all) expect(Object.keys(t).sort()).toEqual(["executed_at", "id", "price", "quantity", "side", "ticker"]);
    const limited = (await (await request.get("/api/portfolio/trades?limit=2")).json()).trades;
    expect(limited.map((t: { ticker: string }) => t.ticker)).toEqual(["NVDA", "MSFT"]);
  });

  test("a trade records a portfolio snapshot", async ({ request }) => {
    await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "buy", quantity: 1 } });
    const res = await request.get("/api/portfolio/history");
    expect(res.status()).toBe(200);
    const { snapshots } = await res.json();
    expect(snapshots.length).toBeGreaterThanOrEqual(1);
    const last = snapshots[snapshots.length - 1];
    expect(typeof last.total_value).toBe("number");
    expect(last.recorded_at).toMatch(/Z$/);
    const times = snapshots.map((s: { recorded_at: string }) => Date.parse(s.recorded_at));
    expect([...times].sort((a, b) => a - b)).toEqual(times);
  });

  test("reset clears positions, trades, snapshots and restores the watchlist", async ({ request }) => {
    await request.post("/api/portfolio/trade", { data: { ticker: "AAPL", side: "buy", quantity: 5 } });
    await request.post("/api/watchlist", { data: { ticker: "PYPL" } });
    await request.delete("/api/watchlist/NFLX");

    const res = await request.post("/api/portfolio/reset");
    expect(res.status()).toBe(200);
    expect(await res.json()).toMatchObject({ cash_balance: 10000, total_value: 10000, positions: [] });
    expect((await (await request.get("/api/portfolio/trades")).json()).trades).toEqual([]);
    expect((await (await request.get("/api/portfolio/history")).json()).snapshots).toEqual([]);
    const wl = (await (await request.get("/api/watchlist")).json()).watchlist.map((w: { ticker: string }) => w.ticker);
    expect([...wl].sort()).toEqual([...DEFAULT_TICKERS].sort());
  });
});
