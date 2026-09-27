import { test, expect, openChat, waitForPrice } from "../fixtures";

// Requires LLM_MOCK=true.
test("AI chat: send a message and get the mock response", async ({ page }) => {
  await page.goto("/");
  await openChat(page);
  await page.getByTestId("chat-input").fill("How is my portfolio doing?");
  await page.getByTestId("chat-send").click();

  await expect(page.locator('[data-testid="chat-message"][data-role="user"]').last()).toContainText(
    "How is my portfolio doing?",
  );
  await expect(page.locator('[data-testid="chat-message"][data-role="assistant"]').last()).toContainText(
    "Mock response: I can help you analyze your portfolio.",
  );
  await expect(page.getByTestId("chat-loading")).toHaveCount(0);
  await expect(page.getByTestId("chat-action")).toHaveCount(0);
});

test("AI chat: trade execution appears inline and updates the portfolio", async ({ page }) => {
  await page.goto("/");
  await waitForPrice(page, "AAPL");

  // Delay the chat response so the loading indicator is observable.
  await page.route("**/api/chat", async (route) => {
    await new Promise((r) => setTimeout(r, 800));
    await route.continue();
  });

  await openChat(page);
  await page.getByTestId("chat-input").fill("buy 3 AAPL");
  await page.getByTestId("chat-send").click();
  await expect(page.getByTestId("chat-loading")).toBeVisible();

  const action = page.getByTestId("chat-action").first();
  await expect(action).toBeVisible();
  await expect(action).toHaveAttribute("data-status", "executed");
  await expect(action).toHaveAttribute("data-kind", "trade");
  await expect(action).toContainText("AAPL");
  await expect(page.getByTestId("chat-loading")).toHaveCount(0);

  await expect(page.getByTestId("position-row-AAPL")).toBeVisible();
  await expect(page.getByTestId("trade-history-row")).toHaveCount(1);
});

test("AI chat: failed trade is shown inline as failed", async ({ page }) => {
  await page.goto("/");
  await openChat(page);
  await page.getByTestId("chat-input").fill("sell 5 TSLA");
  await page.getByTestId("chat-send").click();
  const action = page.getByTestId("chat-action").first();
  await expect(action).toHaveAttribute("data-status", "failed");
  await expect(page.getByTestId("position-row-TSLA")).toHaveCount(0);
});

test("AI chat: watchlist change appears in the watchlist", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByTestId("watchlist-row-AAPL")).toBeVisible();
  await openChat(page);
  await page.getByTestId("chat-input").fill("add PYPL");
  await page.getByTestId("chat-send").click();
  await expect(page.getByTestId("chat-action").first()).toHaveAttribute("data-status", "executed");
  await expect(page.getByTestId("chat-action").first()).toHaveAttribute("data-kind", "watchlist");
  await expect(page.getByTestId("watchlist-row-PYPL")).toBeVisible();
});

test("AI chat: 503 from the assistant shows an error bubble", async ({ page }) => {
  await page.route("**/api/chat", (route) =>
    route.fulfill({
      status: 503,
      contentType: "application/json",
      body: JSON.stringify({ error: "The AI assistant is unavailable right now, please try again shortly." }),
    }),
  );
  await page.goto("/");
  await openChat(page);
  await page.getByTestId("chat-input").fill("hello");
  await page.getByTestId("chat-send").click();
  await expect(page.getByTestId("chat-error")).toBeVisible();
  await expect(page.getByTestId("chat-loading")).toHaveCount(0);
});
