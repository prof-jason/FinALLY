# Frontend data-testids

Owned by `frontend-engineer`. Consumed by `integration-tester` (Playwright). Every id below is stable; anything with `<TICKER>` uses the uppercase symbol (e.g. `watchlist-row-AAPL`).

## Header

| testid | Element | Notes |
|---|---|---|
| `header-total-value` | Live total portfolio value | Text like `$10,000.00`. Recomputed from SSE prices × quantities + cash |
| `header-cash` | Cash balance | Text like `$10,000.00` |
| `header-pnl` | Total unrealized P&L | Text like `+$12.34` / `-$5.00` |
| `connection-status` | Connection dot | `data-status="connected" \| "reconnecting" \| "disconnected"` |
| `reset-button` | Reset portfolio button | Calls `POST /api/portfolio/reset` immediately (no confirm dialog) |

## Watchlist

| testid | Element | Notes |
|---|---|---|
| `watchlist` | Watchlist panel container | |
| `watchlist-row-<TICKER>` | One row per watched ticker | Clicking selects the ticker in the main chart. `data-selected="true"` on the selected row |
| `watchlist-price-<TICKER>` | Price cell | Text like `191.23` (no `$`), `—` until first price. Gets class `flash-up` / `flash-down` briefly on change, and `data-flash="up\|down"` while flashing |
| `watchlist-change-<TICKER>` | Change % cell | Text like `+0.42%` |
| `watchlist-sparkline-<TICKER>` | Sparkline canvas container | |
| `watchlist-remove-<TICKER>` | Remove (×) button in the row | Calls `DELETE /api/watchlist/<TICKER>` |
| `watchlist-add-input` | Add-ticker text input | Uppercases input |
| `watchlist-add-button` | Add-ticker button | Also submits on Enter in the input |
| `watchlist-error` | Inline error from add/remove | Only present when there is an error |

## Main chart

| testid | Element | Notes |
|---|---|---|
| `main-chart` | Main chart panel | `data-ticker="<TICKER>"` = currently selected ticker |
| `main-chart-ticker` | Selected ticker label | Text = ticker symbol |

## Trade bar

| testid | Element | Notes |
|---|---|---|
| `trade-ticker-input` | Ticker input | Pre-filled with the selected ticker when a watchlist row is clicked |
| `trade-quantity-input` | Quantity input | Accepts decimals |
| `trade-buy-button` | Buy button | |
| `trade-sell-button` | Sell button | |
| `trade-error` | Inline error | Present only after a failed trade; text = server `error` message |
| `trade-success` | Inline fill confirmation | Present after a successful trade, e.g. `Bought 2 AAPL @ 191.23` |

## Portfolio

| testid | Element | Notes |
|---|---|---|
| `heatmap` | Treemap container | Always present; shows an empty-state message when no positions |
| `heatmap-cell-<TICKER>` | One rectangle per position | `data-pnl="positive\|negative\|flat"`, background green/red by P&L |
| `pnl-chart` | P&L line chart container | `data-points="<n>"` = number of chart points (snapshots recorded in the same second are merged into one). The chart canvas is hidden until there are at least 2 points |
| `positions-table` | Positions table | |
| `position-row-<TICKER>` | One row per position | |
| `position-qty-<TICKER>` | Quantity cell | |
| `trade-history` | Trade history table | |
| `trade-history-row` | One row per trade (repeated), newest first | `data-ticker`, `data-side="buy\|sell"` |

## Chat

| testid | Element | Notes |
|---|---|---|
| `chat-panel` | Chat sidebar | `data-open="true\|false"` |
| `chat-toggle` | Collapse / expand button | |
| `chat-input` | Message textarea | Enter sends, Shift+Enter newline |
| `chat-send` | Send button | Disabled while a request is in flight |
| `chat-message` | One message bubble (repeated) | `data-role="user\|assistant"` |
| `chat-action` | One inline action result (repeated, inside an assistant message) | `data-status="executed\|failed"`, `data-kind="trade\|watchlist"` |
| `chat-loading` | Loading indicator | Present only while waiting for `/api/chat` |
| `chat-error` | Error bubble when `/api/chat` fails (e.g. 503) | |
