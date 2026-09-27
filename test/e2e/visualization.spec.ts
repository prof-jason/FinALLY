import { test, expect, placeTrade, waitForPrice } from "../fixtures";

test("heatmap shows a cell per position and the P&L chart has data", async ({ page, request }) => {
  await page.goto("/");
  await waitForPrice(page, "AAPL");
  await waitForPrice(page, "MSFT");

  await placeTrade(page, "AAPL", 10, "buy");
  await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
  // The P&L chart merges snapshots within the same second and only draws with >= 2
  // points, so space the trades out to guarantee two distinct points.
  await page.waitForTimeout(1_100);
  await placeTrade(page, "MSFT", 2, "buy");
  await expect(page.getByTestId("position-row-MSFT")).toBeVisible();

  const heatmap = page.getByTestId("heatmap");
  await expect(heatmap).toBeVisible();
  const aapl = page.getByTestId("heatmap-cell-AAPL");
  const msft = page.getByTestId("heatmap-cell-MSFT");
  await expect(aapl).toBeVisible();
  await expect(msft).toBeVisible();

  // Sized by weight: AAPL (10 sh) should dwarf MSFT (2 sh) at similar share prices.
  const a = (await aapl.boundingBox())!;
  const m = (await msft.boundingBox())!;
  expect(a.width * a.height).toBeGreaterThan(m.width * m.height);

  // Colored by P&L: the cell color must agree with the sign of unrealized P&L.
  // We read the live color and the backend P&L; skip the check if P&L is exactly flat.
  await expect.poll(async () => {
    const p = await (await request.get("/api/portfolio")).json();
    const pnl = p.positions.find((x: { ticker: string }) => x.ticker === "AAPL").unrealized_pnl as number;
    const color = await aapl.evaluate((el) => getComputedStyle(el).backgroundColor);
    const [r, g] = (color.match(/\d+(\.\d+)?/g) ?? []).map(Number);
    const sign = await aapl.getAttribute("data-pnl");
    if (Math.abs(pnl) < 0.01) return "flat";
    // P&L drifts with live prices; only judge when backend and UI agree on the sign.
    const expected = pnl > 0 ? "positive" : "negative";
    if (sign !== expected) return `data-pnl=${sign}, backend pnl=${pnl}`;
    return pnl > 0 ? (g > r ? "ok" : `expected green, got ${color}`) : r > g ? "ok" : `expected red, got ${color}`;
  }, { timeout: 15_000 }).toMatch(/^(ok|flat)$/);

  // P&L chart: snapshots exist (one per trade) and the chart renders.
  const { snapshots } = await (await request.get("/api/portfolio/history")).json();
  expect(snapshots.length).toBeGreaterThanOrEqual(2);
  const pnl = page.getByTestId("pnl-chart");
  await expect(pnl).toBeVisible();
  // Reset leaves 0 snapshots, so >= 2 points proves the chart refetched after the trades.
  await expect.poll(async () => Number(await pnl.getAttribute("data-points"))).toBeGreaterThanOrEqual(2);
  await expect(pnl.locator("canvas").first()).toBeVisible();
});

test("heatmap is empty with no positions", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("heatmap")).toBeVisible();
  await expect(page.locator('[data-testid^="heatmap-cell-"]')).toHaveCount(0);
});
