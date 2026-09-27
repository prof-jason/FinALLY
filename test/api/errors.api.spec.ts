import { test, expect } from "../fixtures";
import type { APIResponse } from "@playwright/test";

async function expectError(res: APIResponse, status: number, message?: RegExp) {
  expect(res.status(), await res.text()).toBe(status);
  const body = await res.json();
  expect(Object.keys(body)).toEqual(["error"]);
  expect(typeof body.error).toBe("string");
  expect(body.error.length).toBeGreaterThan(0);
  if (message) expect(body.error).toMatch(message);
}

const trade = (data: object) => ({ data });

test.describe("error contracts", () => {
  for (const ticker of ["AAPL1", "TOOLONG", "", "BRK.B", "A A"]) {
    test(`trade with invalid ticker ${JSON.stringify(ticker)} -> 400`, async ({ request }) => {
      await expectError(await request.post("/api/portfolio/trade", trade({ ticker, side: "buy", quantity: 1 })), 400);
    });
  }

  for (const quantity of [0, -1, -0.5]) {
    test(`trade with quantity ${quantity} -> 400`, async ({ request }) => {
      await expectError(await request.post("/api/portfolio/trade", trade({ ticker: "AAPL", side: "buy", quantity })), 400);
    });
  }

  test("trade with invalid side -> 400", async ({ request }) => {
    await expectError(await request.post("/api/portfolio/trade", trade({ ticker: "AAPL", side: "short", quantity: 1 })), 400);
  });

  test("trade with missing fields -> 400 (validation mapped to 400)", async ({ request }) => {
    await expectError(await request.post("/api/portfolio/trade", trade({ ticker: "AAPL" })), 400);
  });

  test("trade with non-numeric quantity -> 400", async ({ request }) => {
    await expectError(await request.post("/api/portfolio/trade", trade({ ticker: "AAPL", side: "buy", quantity: "lots" })), 400);
  });

  test("insufficient cash -> 400 and nothing changes", async ({ request }) => {
    await expectError(
      await request.post("/api/portfolio/trade", trade({ ticker: "AAPL", side: "buy", quantity: 1_000_000 })),
      400,
      /cash/i,
    );
    const p = await (await request.get("/api/portfolio")).json();
    expect(p.cash_balance).toBe(10000);
    expect(p.positions).toEqual([]);
    expect((await (await request.get("/api/portfolio/trades")).json()).trades).toEqual([]);
  });

  test("selling unheld shares -> 400", async ({ request }) => {
    await expectError(
      await request.post("/api/portfolio/trade", trade({ ticker: "AAPL", side: "sell", quantity: 1 })),
      400,
      /shares/i,
    );
  });

  test("selling more than held -> 400 and position unchanged", async ({ request }) => {
    await request.post("/api/portfolio/trade", trade({ ticker: "AAPL", side: "buy", quantity: 2 }));
    await expectError(
      await request.post("/api/portfolio/trade", trade({ ticker: "AAPL", side: "sell", quantity: 3 })),
      400,
      /shares/i,
    );
    const p = await (await request.get("/api/portfolio")).json();
    expect(p.positions.find((x: { ticker: string }) => x.ticker === "AAPL").quantity).toBeCloseTo(2, 9);
  });

  test("trade for a ticker with no cached price -> 400", async ({ request }) => {
    await expectError(
      await request.post("/api/portfolio/trade", trade({ ticker: "ZZZZ", side: "buy", quantity: 1 })),
      400,
      /No price available for ZZZZ/,
    );
  });

  test("watchlist add with invalid ticker -> 400", async ({ request }) => {
    await expectError(await request.post("/api/watchlist", { data: { ticker: "123" } }), 400);
    await expectError(await request.post("/api/watchlist", { data: {} }), 400);
  });

  test("deleting an unknown watchlist ticker -> 404", async ({ request }) => {
    await expectError(await request.delete("/api/watchlist/ZZZZ"), 404);
  });

  test("chat with missing message -> 400", async ({ request }) => {
    await expectError(await request.post("/api/chat", { data: {} }), 400);
  });
});
