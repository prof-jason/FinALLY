# Market Data Backend — Summary

**Status:** Built, with 145 tests passing and 100% line coverage. Code lives in `backend/app/market/` and tests in `backend/tests/market/`.

Full design: `MARKET_DATA_DESIGN.md`. Where that doc and `PLAN.md` disagree, the code follows `PLAN.md` (see "Deviations" below).

## Architecture

```
MarketDataSource (ABC)
├── SimulatorDataSource  →  GBM simulator (default, no API key needed)
└── MassiveDataSource    →  Massive/Polygon.io REST poller (when MASSIVE_API_KEY set)
        │
        ▼
   PriceCache (thread-safe, in-memory, version counter)
        ├──→ SSE  GET /api/stream/prices
        ├──→ Portfolio valuation
        └──→ Trade execution
```

## Modules

| File | Purpose |
|------|---------|
| `models.py` | `PriceUpdate`: a frozen dataclass whose `change`, `change_percent`, `direction` and `to_dict()` are derived from its fields |
| `cache.py` | `PriceCache`: thread-safe latest-price store. Its `version` is bumped on every update or removal |
| `interface.py` | `MarketDataSource` ABC with `start`, `stop`, `add_ticker`, `remove_ticker`, `get_tickers` |
| `tickers.py` | `normalize_ticker()` (uppercase, `^[A-Z]{1,5}$`), plus `InvalidTickerError` (400), `UnknownTickerError` (404) and `MarketDataError` (503) |
| `seed_prices.py` | Seed prices, per-ticker GBM params and correlation groups |
| `simulator.py` | `GBMSimulator` (Cholesky-correlated GBM with random 2–5% shocks and an optional `seed`) and `SimulatorDataSource` |
| `massive_client.py` | `MassiveDataSource`, plus the parsing helpers `extract_price` and `extract_timestamp` |
| `factory.py` | `create_market_data_source(cache)`: uses Massive if `MASSIVE_API_KEY` is set, otherwise the simulator. `MASSIVE_POLL_INTERVAL` is optional (default 15s) |
| `stream.py` | `create_stream_router(cache)`: builds a fresh router on each call. Sends an SSE event only when the cache version changes |

## Contract for downstream code

```python
from app.market import (
    PriceCache, create_market_data_source, create_stream_router,
    normalize_ticker, InvalidTickerError, UnknownTickerError, MarketDataError,
)

cache = PriceCache()
source = create_market_data_source(cache)
await source.start(tracked_tickers)            # watchlist ∪ open positions
app.include_router(create_stream_router(cache)) # register before static mount

ticker = normalize_ticker(raw)                   # InvalidTickerError -> 400
await source.add_ticker(ticker)                  # UnknownTickerError -> 404, MarketDataError -> 503
price = cache.get_price(ticker)                  # None -> 400 "No price available for X"
await source.remove_ticker(ticker)               # caller decides: only when neither watched nor held
await source.stop()
```

- After `add_ticker` returns, the ticker **always has a cached price**. The simulator seeds it; Massive fetches its snapshot immediately.
- `remove_ticker` also evicts the ticker from the cache. The watchlist/portfolio layer owns the "tracked = watchlist ∪ positions" rule and must not call it while a position is open.
- Each SSE `data:` payload is `{TICKER: {ticker, price, previous_price, timestamp, change, change_percent, direction}}`. It is sent at most every 500ms, and only when something has changed. An empty `{}` is sent after the last ticker is removed.

## Deviations from MARKET_DATA_DESIGN.md

1. **Unknown-ticker seed range is $50–$500**, per PLAN.md; the design doc said $50–$300.
2. **Massive `add_ticker` validates.** It fetches right away, raises `UnknownTickerError` when there is no data, and leaves the ticker untracked. This follows PLAN.md.
3. **Massive snapshot parsing matches the real SDK.** `LastTrade` has no `timestamp` attribute; it has `sip_timestamp`, which is in **nanoseconds**. Its price may be `None`. The code falls back through `last_trade.price` → `min.close` → `day.close` → `prev_day.close`, and converts ns/µs/ms/s timestamps. The design doc's `last_trade.timestamp / 1000` would have dropped every real snapshot.
4. **The Massive poller ignores snapshots for tickers removed mid-request**, so a removed ticker can't come back into the cache.
5. All review items in `MARKET_DATA_REVIEW.md` are addressed:
   - hatch packages config
   - top-level `massive` imports
   - `AsyncGenerator` annotation
   - `version` read under the lock
   - public `GBMSimulator.get_tickers()`
   - per-call router
   - `DEFAULT_CORR` removed
   - SSE, thread-safety and 10-ticker Cholesky tests

## Demo

`backend/market_data_demo.py` is a live Rich terminal dashboard. It shows prices, colored direction arrows, a 40-point sparkline for each ticker, session % change and update rate, plus a log of notable moves (≥1% by default).

```bash
cd backend
uv run market_data_demo.py                     # 60s; simulator unless MASSIVE_API_KEY is exported
uv run market_data_demo.py --duration 0        # run until Ctrl+C
uv run market_data_demo.py --event-prob 0.01   # more random shocks
uv run market_data_demo.py --tickers AAPL TSLA PYPL --threshold 0.5
```

## Tests

```bash
cd backend
uv sync
uv run pytest --cov=app
```

| Module | What it covers |
|--------|----------------|
| test_models.py | derived fields, rounding, immutability, serialization |
| test_tickers.py | regex validation and normalization |
| test_cache.py | direction/previous price, version, removal, concurrent writers |
| test_interface.py | ABC contract; both implementations conform |
| test_simulator.py | exact GBM step formula, statistical drift/vol, empirical correlation, shocks, Cholesky, add/remove |
| test_simulator_source.py | cache seeding, loop updates, add/remove, stop, exception resilience |
| test_massive.py | parsing against real `massive` model objects, polling, error resilience, add validation, removal race |
| test_factory.py | env-var selection, poll interval override |
| test_stream.py | retry directive, change detection, disconnect, empty event, endpoint headers |
