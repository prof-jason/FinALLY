"""Thread-safe in-memory store of the latest price per ticker."""

from __future__ import annotations

import time
from threading import Lock

from .models import PriceUpdate


class PriceCache:
    """Latest price for each tracked ticker.

    Writers: SimulatorDataSource or MassiveDataSource (one at a time).
    Readers: SSE streaming, portfolio valuation, trade execution.

    A `threading.Lock` (not `asyncio.Lock`) is used because the Massive client
    runs its blocking HTTP calls in worker threads via `asyncio.to_thread`.
    """

    def __init__(self) -> None:
        self._prices: dict[str, PriceUpdate] = {}
        self._lock = Lock()
        self._version = 0  # Bumped on every mutation; lets SSE skip unchanged ticks

    def update(self, ticker: str, price: float, timestamp: float | None = None) -> PriceUpdate:
        """Record a new price for a ticker and return the resulting PriceUpdate.

        The first update for a ticker has previous_price == price (direction 'flat').
        """
        with self._lock:
            ts = timestamp if timestamp is not None else time.time()
            prev = self._prices.get(ticker)
            previous_price = prev.price if prev else price

            update = PriceUpdate(
                ticker=ticker,
                price=round(price, 2),
                previous_price=round(previous_price, 2),
                timestamp=ts,
            )
            self._prices[ticker] = update
            self._version += 1
            return update

    def get(self, ticker: str) -> PriceUpdate | None:
        """Latest update for a ticker, or None if unknown."""
        with self._lock:
            return self._prices.get(ticker)

    def get_price(self, ticker: str) -> float | None:
        """Latest price for a ticker, or None if unknown."""
        update = self.get(ticker)
        return update.price if update else None

    def get_all(self) -> dict[str, PriceUpdate]:
        """Shallow copy of all current prices."""
        with self._lock:
            return dict(self._prices)

    def remove(self, ticker: str) -> None:
        """Drop a ticker from the cache. No-op if absent."""
        with self._lock:
            if self._prices.pop(ticker, None) is not None:
                self._version += 1

    @property
    def version(self) -> int:
        """Monotonic counter bumped on every update or removal."""
        with self._lock:
            return self._version

    def __len__(self) -> int:
        with self._lock:
            return len(self._prices)

    def __contains__(self, ticker: object) -> bool:
        with self._lock:
            return ticker in self._prices
