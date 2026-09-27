# FinAlly — Team Contracts

Shared contract for the agent team. `PLAN.md` is the spec; this file fixes **ownership** and the **interfaces between members** so work can proceed in parallel. If you need to change a contract here, message the affected teammates first, then update this file.

## Team & ownership

| Member (agent name) | Owns (only this member edits these) |
|---|---|
| `db-engineer` | `backend/app/db/` (schema SQL, connection, lazy init, seed, repository functions), `backend/tests/db/` |
| `backend-engineer` | `backend/app/main.py`, `backend/app/api/` (routers, error handlers), `backend/app/services/` (trading, watchlist, valuation, tracked tickers, snapshot task), `backend/tests/api/`, `backend/tests/services/`, `backend/pyproject.toml` deps (others ask to add deps) |
| `llm-engineer` | `backend/app/llm/` (schemas, prompt, client, mock, chat service, chat router), `backend/tests/llm/` |
| `frontend-engineer` | `frontend/` (everything, incl. unit tests) |
| `devops-engineer` | `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `.env.example`, `scripts/`, `test/docker-compose.test.yml` |
| `integration-tester` | `test/` Playwright project and specs (except `test/docker-compose.test.yml`) |

`backend/app/market/` is complete — use it via its public API (`planning/MARKET_DATA_SUMMARY.md`); don't modify it without telling the lead.

**Rules:** don't edit files you don't own — message the owner. Don't `git commit`; the lead commits. Run your own unit tests before reporting done. Only free (`:free`) OpenRouter models, never any paid provider.

## Backend Python interfaces

### DB layer — `app.db` (db-engineer)

- DB path: env `FINALLY_DB_PATH`, default `<repo root>/db/finally.db` (Docker sets `/app/db/finally.db`). Parent dir is created if missing.
- `init_db()` — idempotent: creates tables if missing and seeds (`default` user with 10000.0 cash, 10 default tickers) if the user row is missing. Called at app startup.
- Connections: `sqlite3` with `row_factory = sqlite3.Row`, WAL mode. Provide a context manager `get_connection()` and a `transaction()` context manager (commit/rollback) so the trading service can make cash + position + trade + snapshot writes atomic.
- Repository functions (all take `conn` as first arg and `user_id="default"` kwarg; return plain dicts / lists of dicts; timestamps ISO-8601 UTC with `Z`):
  - `get_cash(conn)`, `set_cash(conn, amount)`
  - `list_watchlist(conn)` → `[{ticker, added_at}]` ordered by `added_at`; `add_watchlist(conn, ticker)` (returns False if already present); `remove_watchlist(conn, ticker)` (returns False if absent)
  - `list_positions(conn)`, `get_position(conn, ticker)` → `{ticker, quantity, avg_cost, updated_at}` or None; `upsert_position(conn, ticker, quantity, avg_cost)`; `delete_position(conn, ticker)`
  - `insert_trade(conn, ticker, side, quantity, price)` → trade dict `{id, ticker, side, quantity, price, executed_at}`; `list_trades(conn, limit=100)` newest first
  - `insert_snapshot(conn, total_value)`; `list_snapshots(conn, since)` oldest first; `prune_snapshots(conn, older_than)`
  - `insert_chat_message(conn, role, content, actions: dict | None)`; `list_recent_chat(conn, limit=5)` → oldest-first list of the last N, `actions` decoded from JSON
  - `reset_user(conn)` — the reset described in PLAN §7
- Schema exactly as PLAN §7 (UUID text ids, `user_id` default `"default"`, UNIQUE constraints).
- As built: timestamps have millisecond precision (`2026-09-27T16:03:30.087Z`). `get_connection(db_path=None)` yields an **autocommit** connection (each repo call commits on its own); `transaction(conn=None, db_path=None)` runs BEGIN IMMEDIATE/COMMIT/ROLLBACK, opens its own connection when `conn` is omitted, and joins an already-open transaction. Bool returns: `add_watchlist`/`remove_watchlist`/`delete_position`; `prune_snapshots` returns the deleted count; `upsert_position`/`insert_snapshot`/`insert_chat_message` return the stored dict. `since`/`older_than` accept a datetime or ISO string (`since=None` → all). `insert_snapshot` takes an optional `recorded_at` (for tests). Tickers are stored as given; normalization is the service layer's job.

### Services — `app.services` (backend-engineer)

Used by the API routes **and** by the LLM chat service. Errors raise `ServiceError(message, status_code)` (400/404/503) which the API layer maps to `{"error": message}`.

- `execute_trade(ticker: str, side: str, quantity: float) -> dict` → `{"trade": {...}, "portfolio": {...}}`. Validates per PLAN §8 (normalize ticker, qty > 0, side, cached price, cash, shares, 1e-9 zero rule), writes atomically, records a snapshot, and untracks the ticker from the market source if it is now neither watched nor held.
- `add_watchlist_ticker(ticker: str) -> dict` (calls `source.add_ticker`; 409-free: adding an existing ticker is a no-op success) and `remove_watchlist_ticker(ticker: str) -> None` (404 if not on watchlist; keeps tracking while held).
- `get_portfolio() -> dict`, `get_watchlist() -> list[dict]`, `reset_portfolio() -> dict`.
- Access to the shared `PriceCache` / `MarketDataSource` via `app.services.state` (module-level holder set in the FastAPI lifespan) — backend-engineer defines it; LLM code reads through it.

### LLM — `app.llm` (llm-engineer)

- `create_chat_router() -> APIRouter` exposing `POST /api/chat` (`{message}` → PLAN §8 Chat Response Contract). `backend-engineer` includes it in `main.py`.
- Uses `app.services` for execution (watchlist changes first, then trades, each independent) and `app.db` for history. `LLM_MOCK=true` → deterministic mock (see below). LLM/rate-limit failures → `503 {"error": "The AI assistant is unavailable right now, please try again shortly."}`.
- **Mock contract (for E2E):** if the message contains `buy <qty> <TICKER>` / `sell <qty> <TICKER>` (case-insensitive) the mock emits that trade; `add <TICKER>` / `remove <TICKER>` emit watchlist changes; otherwise it returns a fixed message `"Mock response: I can help you analyze your portfolio."` with no actions.

## HTTP API shapes (backend-engineer implements, frontend + tester consume)

All errors: `{"error": "..."}` (including request-validation errors, mapped to 400).

- `GET /api/health` → `{"status": "ok"}`
- `GET /api/portfolio` →
  ```json
  {"cash_balance": 10000.0, "total_value": 10000.0, "total_unrealized_pnl": 0.0,
   "positions": [{"ticker": "AAPL", "quantity": 2.5, "avg_cost": 190.1, "current_price": 191.2,
                  "market_value": 478.0, "unrealized_pnl": 2.75, "unrealized_pnl_percent": 0.58}]}
  ```
  `current_price` falls back to `avg_cost` if no cached price.
- `POST /api/portfolio/trade` → `{"trade": {...}, "portfolio": {...}}` (PLAN §8)
- `GET /api/portfolio/history` → `{"snapshots": [{"total_value": 10000.0, "recorded_at": "…Z"}]}` oldest first, last 10 days
- `GET /api/portfolio/trades?limit=100` → `{"trades": [{id, ticker, side, quantity, price, executed_at}]}` newest first
- `POST /api/portfolio/reset` → portfolio object (same as GET)
- `GET /api/watchlist` → `{"watchlist": [{"ticker", "price", "previous_price", "change", "change_percent", "direction", "added_at"}]}` (price fields null if no cached price)
- `POST /api/watchlist` `{ticker}` → `201` with the watchlist item; `DELETE /api/watchlist/{ticker}` → `204`
- `POST /api/chat` → PLAN §8 Chat Response Contract
- `GET /api/stream/prices` → SSE, payload `{TICKER: {ticker, price, previous_price, timestamp, change, change_percent, direction}}`

## Frontend ↔ E2E selectors (frontend-engineer defines, integration-tester consumes)

Frontend adds stable `data-testid`s and lists them in `planning/FRONTEND_TESTIDS.md`. Minimum: `header-total-value`, `header-cash`, `connection-status` (with `data-status="connected|reconnecting|disconnected"`), `reset-button`, `watchlist-row-<TICKER>`, `watchlist-price-<TICKER>`, `watchlist-add-input`, `watchlist-add-button`, `watchlist-remove-<TICKER>`, `trade-ticker-input`, `trade-quantity-input`, `trade-buy-button`, `trade-sell-button`, `trade-error`, `position-row-<TICKER>`, `trade-history-row` (repeated), `heatmap`, `heatmap-cell-<TICKER>`, `pnl-chart`, `main-chart`, `chat-input`, `chat-send`, `chat-message` (repeated, with `data-role`), `chat-action` (repeated, with `data-status`), `chat-loading`.

## Runtime layout (devops-engineer)

- Frontend: Next.js static export → `frontend/out/`. Docker copies it to `/app/static`; FastAPI mounts `StaticFiles(directory=<static dir>, html=True)` at `/` last, where the static dir is env `FINALLY_STATIC_DIR` (default `backend/static`, only mounted if it exists).
- Container: `WORKDIR /app`, backend at `/app`, `uvicorn app.main:app --host 0.0.0.0 --port 8000`, volume `finally-data:/app/db`, `FINALLY_DB_PATH=/app/db/finally.db`.
- Local dev: backend `cd backend && uv run uvicorn app.main:app --reload --port 8000`; frontend `npm run dev` with a Next rewrite of `/api/*` → `http://localhost:8000` (dev only).
