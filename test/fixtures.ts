import { test as base, expect, APIRequestContext, Page } from "@playwright/test";

export const DEFAULT_TICKERS = ["AAPL", "GOOGL", "MSFT", "AMZN", "TSLA", "NVDA", "META", "JPM", "V", "NFLX"];

/** Restore the seed state (PLAN §7). Every spec calls this in setup. */
export async function resetPortfolio(request: APIRequestContext) {
  const res = await request.post("/api/portfolio/reset");
  expect(res.status(), await res.text()).toBe(200);
  return res.json();
}

/** "$10,000.00" / "-$12.34" / "10000" -> number */
export function parseMoney(text: string | null): number {
  const cleaned = (text ?? "").replace(/[^0-9.\-]/g, "");
  const value = Number(cleaned);
  if (cleaned === "" || Number.isNaN(value)) throw new Error(`Not a number: ${JSON.stringify(text)}`);
  return value;
}

export async function textNumber(page: Page, testId: string): Promise<number> {
  return parseMoney(await page.getByTestId(testId).textContent());
}

/** Wait until the SSE feed has delivered a price for `ticker` into the watchlist row. */
export async function waitForPrice(page: Page, ticker: string) {
  await expect
    .poll(async () => {
      const text = (await page.getByTestId(`watchlist-price-${ticker}`).textContent()) ?? "";
      return /\d/.test(text);
    }, { timeout: 15_000 })
    .toBe(true);
}

/** Fill the trade bar and submit. */
export async function placeTrade(page: Page, ticker: string, quantity: number | string, side: "buy" | "sell") {
  await page.getByTestId("trade-ticker-input").fill(ticker);
  await page.getByTestId("trade-quantity-input").fill(String(quantity));
  await page.getByTestId(side === "buy" ? "trade-buy-button" : "trade-sell-button").click();
}

/** Expand the chat sidebar if it is collapsed. */
export async function openChat(page: Page) {
  const panel = page.getByTestId("chat-panel");
  await expect(panel).toBeAttached();
  if ((await panel.getAttribute("data-open")) === "false") await page.getByTestId("chat-toggle").click();
  await expect(page.getByTestId("chat-input")).toBeVisible();
}

type Fixtures = { resetState: void };

/** `test` with an auto fixture that resets the shared DB before each test. */
export const test = base.extend<Fixtures>({
  resetState: [
    async ({ request }, use) => {
      await resetPortfolio(request);
      await use();
    },
    { auto: true },
  ],
});

export { expect };
