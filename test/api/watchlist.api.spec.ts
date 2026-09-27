import { test, expect, DEFAULT_TICKERS } from "../fixtures";
import { collectPriceEvents } from "../sse";

const tickers = async (request: import("@playwright/test").APIRequestContext) =>
  (await (await request.get("/api/watchlist")).json()).watchlist.map((w: { ticker: string }) => w.ticker) as string[];

test.describe("watchlist API", () => {
  test("default watchlist has the 10 seed tickers with prices", async ({ request }) => {
    const res = await request.get("/api/watchlist");
    expect(res.status()).toBe(200);
    const { watchlist } = await res.json();
    expect(watchlist.map((w: { ticker: string }) => w.ticker).sort()).toEqual([...DEFAULT_TICKERS].sort());
    for (const item of watchlist) {
      for (const key of ["ticker", "price", "previous_price", "change", "change_percent", "direction", "added_at"]) {
        expect(item).toHaveProperty(key);
      }
    }
    // The simulator seeds all default tickers immediately.
    expect(watchlist.every((w: { price: number | null }) => typeof w.price === "number" && w.price > 0)).toBe(true);
  });

  test("add returns 201 with the item and it gets a price immediately", async ({ request }) => {
    const res = await request.post("/api/watchlist", { data: { ticker: "pypl" } });
    expect(res.status(), await res.text()).toBe(201);
    const item = await res.json();
    expect(item.ticker).toBe("PYPL");
    expect(await tickers(request)).toContain("PYPL");
    const wl = (await (await request.get("/api/watchlist")).json()).watchlist;
    expect(wl.find((w: { ticker: string }) => w.ticker === "PYPL").price).toBeGreaterThan(0);
  });

  test("adding an existing ticker is a no-op success", async ({ request }) => {
    const res = await request.post("/api/watchlist", { data: { ticker: "AAPL" } });
    expect([200, 201]).toContain(res.status());
    expect((await tickers(request)).filter((t) => t === "AAPL")).toHaveLength(1);
  });

  test("delete returns 204 and removes the ticker", async ({ request }) => {
    const res = await request.delete("/api/watchlist/NFLX");
    expect(res.status()).toBe(204);
    expect(await tickers(request)).not.toContain("NFLX");
  });

  test("SSE streams all watchlist tickers with the documented fields", async ({ baseURL }) => {
    const { events, contentType } = await collectPriceEvents(baseURL!, (ev) =>
      ev.some((e) => DEFAULT_TICKERS.every((t) => t in e)),
    );
    expect(contentType).toContain("text/event-stream");
    const full = events.find((e) => DEFAULT_TICKERS.every((t) => t in e))!;
    expect(full, "no event contained all default tickers").toBeTruthy();
    for (const key of ["ticker", "price", "previous_price", "timestamp", "change", "change_percent", "direction"]) {
      expect(full.AAPL).toHaveProperty(key);
    }
  });

  test("SSE sends repeated updates (prices are streaming)", async ({ baseURL }) => {
    const { events } = await collectPriceEvents(baseURL!, (ev) => ev.length >= 3, 10_000);
    expect(events.length).toBeGreaterThanOrEqual(3);
  });

  test("tracked set: a removed-but-held ticker keeps streaming until sold", async ({ request, baseURL }) => {
    await request.post("/api/watchlist", { data: { ticker: "PYPL" } });
    const buy = await request.post("/api/portfolio/trade", { data: { ticker: "PYPL", side: "buy", quantity: 1 } });
    expect(buy.status(), await buy.text()).toBe(200);
    expect((await request.delete("/api/watchlist/PYPL")).status()).toBe(204);
    expect(await tickers(request)).not.toContain("PYPL");

    // Still tracked while held.
    let { events } = await collectPriceEvents(baseURL!, (ev) => ev.length >= 2);
    expect(events.at(-1)).toHaveProperty("PYPL");
    // Can still be sold (price is still cached).
    const sell = await request.post("/api/portfolio/trade", { data: { ticker: "PYPL", side: "sell", quantity: 1 } });
    expect(sell.status(), await sell.text()).toBe(200);

    // Neither watched nor held -> no longer tracked.
    ({ events } = await collectPriceEvents(baseURL!, (ev) => ev.length >= 2));
    expect(events.at(-1)).not.toHaveProperty("PYPL");
  });

  test("buying an unwatched ticker that has no price is rejected", async ({ request }) => {
    const res = await request.post("/api/portfolio/trade", { data: { ticker: "QQQQ", side: "buy", quantity: 1 } });
    expect(res.status()).toBe(400);
  });
});
