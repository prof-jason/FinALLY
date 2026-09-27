import { test, expect, waitForPrice } from "../fixtures";

test("add and remove a ticker from the watchlist", async ({ page, request }) => {
  await page.goto("/");
  await expect(page.getByTestId("watchlist-row-AAPL")).toBeVisible();

  await page.getByTestId("watchlist-add-input").fill("pypl");
  await page.getByTestId("watchlist-add-button").click();
  await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();
  await waitForPrice(page, "PYPL");

  const wl = (await (await request.get("/api/watchlist")).json()).watchlist.map((w: { ticker: string }) => w.ticker);
  expect(wl).toContain("PYPL");

  await page.getByTestId("watchlist-remove-PYPL").click();
  await expect(page.getByTestId("watchlist-row-PYPL")).toHaveCount(0);
  await page.getByTestId("watchlist-remove-NFLX").click();
  await expect(page.getByTestId("watchlist-row-NFLX")).toHaveCount(0);

  const after = (await (await request.get("/api/watchlist")).json()).watchlist.map((w: { ticker: string }) => w.ticker);
  expect(after).not.toContain("PYPL");
  expect(after).not.toContain("NFLX");

  // Persisted across reload.
  await page.reload();
  await expect(page.getByTestId("watchlist-row-AAPL")).toBeVisible();
  await expect(page.getByTestId("watchlist-row-NFLX")).toHaveCount(0);
});

test("adding an invalid ticker does not add a row", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("watchlist-row-AAPL")).toBeVisible();
  await page.getByTestId("watchlist-add-input").fill("NOT-A-TICKER");
  await page.getByTestId("watchlist-add-button").click();
  await expect(page.getByTestId("watchlist-error")).toBeVisible();
  await expect(page.locator('[data-testid^="watchlist-row-"]')).toHaveCount(10);
});
