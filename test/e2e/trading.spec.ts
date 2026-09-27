import { test, expect, placeTrade, textNumber, waitForPrice } from "../fixtures";

test.beforeEach(async ({ page }) => {
  await page.goto("/");
  await waitForPrice(page, "AAPL");
});

test("buy shares: cash decreases, position appears, history updates", async ({ page }) => {
  await placeTrade(page, "AAPL", 5, "buy");

  const row = page.getByTestId("position-row-AAPL");
  await expect(row).toBeVisible();
  await expect(page.getByTestId("position-qty-AAPL")).toHaveText(/^\s*5(\.0+)?\s*$/);
  await expect(page.getByTestId("trade-success")).toContainText("AAPL");
  await expect.poll(() => textNumber(page, "header-cash")).toBeLessThan(10000);
  await expect(page.getByTestId("trade-history-row")).toHaveCount(1);
  await expect(page.getByTestId("trade-history-row").first()).toHaveAttribute("data-ticker", "AAPL");
  await expect(page.getByTestId("trade-history-row").first()).toHaveAttribute("data-side", "buy");
});

test("sell shares: partial sell updates the position, full sell removes it", async ({ page, request }) => {
  await placeTrade(page, "AAPL", 10, "buy");
  await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
  const cashAfterBuy = (await (await request.get("/api/portfolio")).json()).cash_balance;
  await expect.poll(() => textNumber(page, "header-cash")).toBeCloseTo(cashAfterBuy, 1);

  await placeTrade(page, "AAPL", 4, "sell");
  await expect.poll(() => textNumber(page, "header-cash")).toBeGreaterThan(cashAfterBuy);
  const p = await (await request.get("/api/portfolio")).json();
  expect(p.positions[0].quantity).toBeCloseTo(6, 9);
  await expect(page.getByTestId("position-qty-AAPL")).toHaveText(/^\s*6(\.0+)?\s*$/);

  await placeTrade(page, "AAPL", 6, "sell");
  await expect(page.getByTestId("position-row-AAPL")).toHaveCount(0);
  await expect(page.getByTestId("trade-history-row")).toHaveCount(3);
});

test("fractional quantities are accepted", async ({ page, request }) => {
  await placeTrade(page, "AAPL", "0.5", "buy");
  await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
  const p = await (await request.get("/api/portfolio")).json();
  expect(p.positions[0].quantity).toBeCloseTo(0.5, 9);
});

test("insufficient cash shows a trade error", async ({ page }) => {
  await placeTrade(page, "AAPL", 1000000, "buy");
  await expect(page.getByTestId("trade-error")).toBeVisible();
  await expect(page.getByTestId("trade-error")).toContainText(/cash/i);
  await expect(page.getByTestId("position-row-AAPL")).toHaveCount(0);
});

test("selling unheld shares shows a trade error", async ({ page }) => {
  await placeTrade(page, "TSLA", 1, "sell");
  await expect(page.getByTestId("trade-error")).toBeVisible();
  await expect(page.getByTestId("trade-error")).toContainText(/shares/i);
});

test("trade history lists trades newest first", async ({ page }) => {
  await placeTrade(page, "AAPL", 1, "buy");
  await expect(page.getByTestId("trade-history-row")).toHaveCount(1);
  await placeTrade(page, "MSFT", 2, "buy");
  await expect(page.getByTestId("trade-history-row")).toHaveCount(2);
  await placeTrade(page, "AAPL", 1, "sell");
  const rows = page.getByTestId("trade-history-row");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0)).toHaveAttribute("data-ticker", "AAPL");
  await expect(rows.nth(0)).toHaveAttribute("data-side", "sell");
  await expect(rows.nth(1)).toHaveAttribute("data-ticker", "MSFT");
  await expect(rows.nth(2)).toHaveAttribute("data-ticker", "AAPL");
  await expect(rows.nth(2)).toHaveAttribute("data-side", "buy");
});
