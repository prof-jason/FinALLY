"""MarketDataSource backed by the Massive (formerly Polygon.io) REST API."""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from massive import RESTClient
from massive.rest.models import SnapshotMarketType

from .cache import PriceCache
from .interface import MarketDataSource
from .tickers import MarketDataError, UnknownTickerError

logger = logging.getLogger(__name__)


def extract_price(snap: Any) -> float | None:
    """Best available price from a TickerSnapshot, or None if it has none.

    Prefers the last trade, then the latest minute bar, today's bar, and
    finally the previous day's close (e.g. before the first trade of the day).
    """
    candidates = (
        (getattr(snap, "last_trade", None), "price"),
        (getattr(snap, "min", None), "close"),
        (getattr(snap, "day", None), "close"),
        (getattr(snap, "prev_day", None), "close"),
    )
    for obj, attr in candidates:
        value = getattr(obj, attr, None) if obj is not None else None
        if isinstance(value, (int, float)) and value > 0:
            return float(value)
    return None


def to_unix_seconds(ts: Any) -> float | None:
    """Convert a Massive timestamp (ns, us, ms or s since epoch) to Unix seconds."""
    if not isinstance(ts, (int, float)) or ts <= 0:
        return None
    if ts >= 1e17:  # nanoseconds
        return ts / 1e9
    if ts >= 1e14:  # microseconds
        return ts / 1e6
    if ts >= 1e11:  # milliseconds
        return ts / 1e3
    return float(ts)


def extract_timestamp(snap: Any) -> float:
    """Timestamp of the snapshot's price in Unix seconds, falling back to now."""
    last_trade = getattr(snap, "last_trade", None)
    for ts in (
        getattr(last_trade, "sip_timestamp", None) if last_trade is not None else None,
        getattr(snap, "updated", None),
    ):
        seconds = to_unix_seconds(ts)
        if seconds is not None:
            return seconds
    return time.time()


class MassiveDataSource(MarketDataSource):
    """Polls the Massive snapshot endpoint for all tracked tickers in one call.

    Rate limits:
      - Free tier: 5 req/min -> poll every 15s (default)
      - Paid tiers: poll every 2-15s
    """

    def __init__(
        self,
        api_key: str,
        price_cache: PriceCache,
        poll_interval: float = 15.0,
        client: Any | None = None,
    ) -> None:
        self._api_key = api_key
        self._cache = price_cache
        self._interval = poll_interval
        self._client: Any = client
        self._tickers: list[str] = []
        self._task: asyncio.Task | None = None

    async def start(self, tickers: list[str]) -> None:
        if self._client is None:
            self._client = RESTClient(api_key=self._api_key)
        self._tickers = list(dict.fromkeys(tickers))

        # Immediate first poll so the cache has data right away
        await self._poll_once()

        self._task = asyncio.create_task(self._poll_loop(), name="massive-poller")
        logger.info(
            "Massive poller started: %d tickers, %.1fs interval",
            len(self._tickers),
            self._interval,
        )

    async def stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._task = None
        logger.info("Massive poller stopped")

    async def add_ticker(self, ticker: str) -> None:
        """Fetch the ticker's snapshot now; reject it if Massive has no data.

        Raises UnknownTickerError if Massive returns no usable price, and
        MarketDataError if the API call itself fails. Nothing is tracked in
        either case.
        """
        if ticker in self._tickers:
            return
        if self._client is None:
            raise RuntimeError("MassiveDataSource.add_ticker called before start()")

        try:
            snapshots = await asyncio.to_thread(self._fetch_snapshots, [ticker])
        except Exception as e:
            raise MarketDataError(f"Market data lookup failed for {ticker}: {e}") from e

        snap = next((s for s in snapshots if getattr(s, "ticker", None) == ticker), None)
        price = extract_price(snap) if snap is not None else None
        if price is None:
            raise UnknownTickerError(ticker)

        self._tickers.append(ticker)
        self._cache.update(ticker=ticker, price=price, timestamp=extract_timestamp(snap))
        logger.info("Massive: added ticker %s at %.2f", ticker, price)

    async def remove_ticker(self, ticker: str) -> None:
        self._tickers = [t for t in self._tickers if t != ticker]
        self._cache.remove(ticker)
        logger.info("Massive: removed ticker %s", ticker)

    def get_tickers(self) -> list[str]:
        return list(self._tickers)

    # --- Internal ---

    async def _poll_loop(self) -> None:
        """Poll on an interval. The first poll already happened in start()."""
        while True:
            await asyncio.sleep(self._interval)
            await self._poll_once()

    async def _poll_once(self) -> None:
        """Fetch snapshots for all tracked tickers and write them to the cache.

        Never raises: API errors (401, 429, network) are logged and the next
        cycle retries. Snapshots without a usable price are skipped.
        """
        tickers = list(self._tickers)
        if not tickers or self._client is None:
            return

        try:
            snapshots = await asyncio.to_thread(self._fetch_snapshots, tickers)
        except Exception as e:
            logger.error("Massive poll failed: %s", e)
            return

        processed = 0
        for snap in snapshots:
            ticker = getattr(snap, "ticker", None)
            # Skip tickers removed while the request was in flight
            if ticker not in self._tickers:
                continue
            price = extract_price(snap)
            if price is None:
                logger.warning("Skipping snapshot for %s: no price", ticker)
                continue
            self._cache.update(ticker=ticker, price=price, timestamp=extract_timestamp(snap))
            processed += 1
        logger.debug("Massive poll: updated %d/%d tickers", processed, len(tickers))

    def _fetch_snapshots(self, tickers: list[str]) -> list:
        """Blocking Massive API call. Runs in a worker thread."""
        return self._client.get_snapshot_all(
            market_type=SnapshotMarketType.STOCKS,
            tickers=tickers,
        )
