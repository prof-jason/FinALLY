import { test, expect } from "../fixtures";

// Requires the backend to run with LLM_MOCK=true (see TEAM_CONTRACTS mock contract).
const MOCK_TEXT = "Mock response: I can help you analyze your portfolio.";

test.describe("chat API (mock LLM)", () => {
  test("plain message returns the fixed mock text and no actions", async ({ request }) => {
    const res = await request.post("/api/chat", { data: { message: "How is my portfolio doing?" } });
    expect(res.status(), await res.text()).toBe(200);
    const body = await res.json();
    expect(body.message).toBe(MOCK_TEXT);
    const trades = body.actions?.trades ?? [];
    const wl = body.actions?.watchlist_changes ?? [];
    expect(trades).toEqual([]);
    expect(wl).toEqual([]);
  });

  test("buy instruction executes a trade", async ({ request }) => {
    const res = await request.post("/api/chat", { data: { message: "please buy 2 AAPL" } });
    expect(res.status(), await res.text()).toBe(200);
    const { message, actions } = await res.json();
    expect(typeof message).toBe("string");
    expect(actions.trades).toHaveLength(1);
    expect(actions.trades[0]).toMatchObject({ ticker: "AAPL", side: "buy", quantity: 2, status: "executed" });
    expect(actions.trades[0].price).toBeGreaterThan(0);
    const p = await (await request.get("/api/portfolio")).json();
    expect(p.positions.find((x: { ticker: string }) => x.ticker === "AAPL").quantity).toBeCloseTo(2, 9);
  });

  test("failing trade reports status failed with error; others still run", async ({ request }) => {
    const res = await request.post("/api/chat", { data: { message: "add PYPL and buy 1000000 AAPL" } });
    expect(res.status(), await res.text()).toBe(200);
    const { actions } = await res.json();
    expect(actions.watchlist_changes[0]).toMatchObject({ ticker: "PYPL", action: "add", status: "executed" });
    expect(actions.trades[0]).toMatchObject({ ticker: "AAPL", side: "buy", status: "failed" });
    expect(actions.trades[0].error).toMatch(/cash/i);
    const wl = (await (await request.get("/api/watchlist")).json()).watchlist.map((w: { ticker: string }) => w.ticker);
    expect(wl).toContain("PYPL");
  });

  test("sell instruction on unheld shares fails gracefully", async ({ request }) => {
    const res = await request.post("/api/chat", { data: { message: "sell 5 TSLA" } });
    expect(res.status()).toBe(200);
    const { actions } = await res.json();
    expect(actions.trades[0]).toMatchObject({ ticker: "TSLA", side: "sell", status: "failed" });
  });

  test("remove instruction removes from watchlist", async ({ request }) => {
    const res = await request.post("/api/chat", { data: { message: "remove NFLX" } });
    expect(res.status()).toBe(200);
    const { actions } = await res.json();
    expect(actions.watchlist_changes[0]).toMatchObject({ ticker: "NFLX", action: "remove", status: "executed" });
  });
});
