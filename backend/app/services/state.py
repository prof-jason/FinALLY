"""Process-wide holder for the shared PriceCache and MarketDataSource.

Set once in the FastAPI lifespan via `configure()`; read by the services and
the LLM chat service. `mutation_lock` serializes writes that also change the
set of tracked tickers (trades, watchlist edits, reset), so the
"tracked = watchlist ∪ positions" decision never races.
"""

from __future__ import annotations

import asyncio

from app.market import MarketDataSource, PriceCache

_price_cache: PriceCache | None = None
_market_source: MarketDataSource | None = None
_mutation_lock: asyncio.Lock | None = None


def configure(price_cache: PriceCache, market_source: MarketDataSource) -> None:
    """Install the shared cache and source (called from the app lifespan)."""
    global _price_cache, _market_source, _mutation_lock
    _price_cache = price_cache
    _market_source = market_source
    _mutation_lock = asyncio.Lock()


def clear() -> None:
    """Forget the cache and source (called on shutdown and in tests)."""
    global _price_cache, _market_source, _mutation_lock
    _price_cache = None
    _market_source = None
    _mutation_lock = None


def get_price_cache() -> PriceCache:
    if _price_cache is None:
        raise RuntimeError("Market data state is not configured")
    return _price_cache


def get_market_source() -> MarketDataSource:
    if _market_source is None:
        raise RuntimeError("Market data state is not configured")
    return _market_source


def mutation_lock() -> asyncio.Lock:
    if _mutation_lock is None:
        raise RuntimeError("Market data state is not configured")
    return _mutation_lock
