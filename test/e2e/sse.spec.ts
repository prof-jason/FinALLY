import { test, expect, waitForPrice } from "../fixtures";

const STREAM = "**/api/stream/prices";

test("SSE resilience: status reflects a dropped stream and recovers when the server is back", async ({ page }) => {
  // Record every EventSource so the test can sever the live one. (context.setOffline
  // does not drop an already-open stream in Chromium.)
  await page.addInitScript(() => {
    const Native = window.EventSource;
    const instances: EventSource[] = [];
    (window as unknown as { __eventSources: EventSource[] }).__eventSources = instances;
    window.EventSource = class extends Native {
      constructor(url: string | URL, init?: EventSourceInit) {
        super(url, init);
        instances.push(this);
      }
    } as typeof EventSource;
  });

  await page.goto("/");
  const status = page.getByTestId("connection-status");
  await expect(status).toHaveAttribute("data-status", "connected");
  await waitForPrice(page, "AAPL");

  // Server "goes away": new connections fail, and the live stream errors out.
  await page.route(STREAM, (route) => route.abort("connectionrefused"));
  await page.evaluate(() => {
    for (const es of (window as unknown as { __eventSources: EventSource[] }).__eventSources) {
      if (es.readyState !== EventSource.CLOSED) {
        es.close();
        es.dispatchEvent(new Event("error"));
      }
    }
  });
  await expect(status).toHaveAttribute("data-status", /reconnecting|disconnected/);
  // Stays down while the server is unreachable (reconnect attempts keep failing).
  await page.waitForTimeout(4_000);
  await expect(status).toHaveAttribute("data-status", /reconnecting|disconnected/);

  // Server is back: the client reconnects on its own and prices resume.
  await page.unroute(STREAM);
  await expect(status).toHaveAttribute("data-status", "connected", { timeout: 20_000 });
  const tickers = ["AAPL", "MSFT", "NVDA", "TSLA"];
  const prices = () => Promise.all(tickers.map((t) => page.getByTestId(`watchlist-price-${t}`).textContent()));
  const start = await prices();
  await expect.poll(async () => (await prices()).some((p, i) => p !== start[i]), { timeout: 15_000 }).toBe(true);
});
