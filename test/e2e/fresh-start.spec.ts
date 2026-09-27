import { test, expect, DEFAULT_TICKERS, textNumber, waitForPrice } from "../fixtures";

test("fresh start: default watchlist, $10k, prices streaming, connected", async ({ page }) => {
  await page.goto("/");

  for (const ticker of DEFAULT_TICKERS) {
    await expect(page.getByTestId(`watchlist-row-${ticker}`)).toBeVisible();
  }
  await expect(page.locator('[data-testid^="watchlist-row-"]')).toHaveCount(DEFAULT_TICKERS.length);

  await expect.poll(() => textNumber(page, "header-cash")).toBe(10000);
  await expect.poll(() => textNumber(page, "header-total-value")).toBe(10000);

  await expect(page.getByTestId("connection-status")).toHaveAttribute("data-status", "connected");

  // Prices stream: at least one of the watchlist prices changes within a few seconds.
  for (const t of DEFAULT_TICKERS) await waitForPrice(page, t);
  const snapshot = async () =>
    Promise.all(DEFAULT_TICKERS.map((t) => page.getByTestId(`watchlist-price-${t}`).textContent()));
  const initial = await snapshot();
  await expect.poll(async () => (await snapshot()).some((p, i) => p !== initial[i]), { timeout: 15_000 }).toBe(true);
});

test("clicking a watchlist ticker shows the main chart", async ({ page }) => {
  await page.goto("/");
  await page.getByTestId("watchlist-row-MSFT").click();
  const chart = page.getByTestId("main-chart");
  await expect(chart).toBeVisible();
  await expect(chart).toHaveAttribute("data-ticker", "MSFT");
  await expect(page.getByTestId("main-chart-ticker")).toHaveText("MSFT");
  await expect(page.getByTestId("watchlist-row-MSFT")).toHaveAttribute("data-selected", "true");
  await expect(page.getByTestId("trade-ticker-input")).toHaveValue("MSFT");
  await expect(chart.locator("canvas").first()).toBeVisible();
});

test("price changes flash the price cell", async ({ page }) => {
  await page.goto("/");
  await waitForPrice(page, "AAPL");
  // Flashes last ~250ms on a ~500ms tick, and Playwright's 1s assertion polling can
  // phase-lock onto the gap between them, so observe mutations in the page instead.
  const flash = await page.evaluate(
    () =>
      new Promise<{ dir: string | null; className: string }>((resolve, reject) => {
        const cells = document.querySelectorAll('[data-testid^="watchlist-price-"]');
        const timer = setTimeout(() => reject(new Error("no price cell flashed within 15s")), 15_000);
        const observer = new MutationObserver((mutations) => {
          for (const m of mutations) {
            const el = m.target as HTMLElement;
            if (el.hasAttribute("data-flash")) {
              clearTimeout(timer);
              observer.disconnect();
              resolve({ dir: el.getAttribute("data-flash"), className: el.className });
              return;
            }
          }
        });
        cells.forEach((c) => observer.observe(c, { attributes: true, attributeFilter: ["data-flash"] }));
      }),
  );
  expect(flash.dir).toMatch(/^(up|down)$/);
  expect(flash.className).toContain(`flash-${flash.dir}`);
});

test("sparklines render for watched tickers", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("watchlist-sparkline-AAPL")).toBeVisible();
});
