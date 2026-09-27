import { test, expect, DEFAULT_TICKERS, placeTrade, textNumber, waitForPrice } from "../fixtures";

test("reset restores $10k, empty positions, empty history and the default watchlist", async ({ page }) => {
  await page.goto("/");
  await waitForPrice(page, "AAPL");

  await placeTrade(page, "AAPL", 3, "buy");
  await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
  await page.getByTestId("watchlist-add-input").fill("PYPL");
  await page.getByTestId("watchlist-add-button").click();
  await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();
  await page.getByTestId("watchlist-remove-NFLX").click();
  await expect(page.getByTestId("watchlist-row-NFLX")).toHaveCount(0);

  page.on("dialog", (d) => d.accept()); // in case the UI confirms
  await page.getByTestId("reset-button").click();

  await expect.poll(() => textNumber(page, "header-cash")).toBe(10000);
  await expect.poll(() => textNumber(page, "header-total-value")).toBe(10000);
  await expect(page.locator('[data-testid^="position-row-"]')).toHaveCount(0);
  await expect(page.getByTestId("trade-history-row")).toHaveCount(0);
  await expect(page.getByTestId("watchlist-row-PYPL")).toHaveCount(0);
  for (const t of DEFAULT_TICKERS) await expect(page.getByTestId(`watchlist-row-${t}`)).toBeVisible();
  await expect(page.locator('[data-testid^="watchlist-row-"]')).toHaveCount(DEFAULT_TICKERS.length);
});
