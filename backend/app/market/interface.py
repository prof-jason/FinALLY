"""Abstract contract every market data provider implements."""

from __future__ import annotations

from abc import ABC, abstractmethod


class MarketDataSource(ABC):
    """Contract for market data providers.

    Implementations push price updates into a shared PriceCache on their own
    schedule. Downstream code never asks the source for prices — it reads the
    cache.

    Lifecycle:
        source = create_market_data_source(cache)
        await source.start(["AAPL", "GOOGL", ...])
        await source.add_ticker("TSLA")
        await source.remove_ticker("GOOGL")
        await source.stop()

    Tickers passed in are expected to be normalized already (see `tickers.py`).
    """

    @abstractmethod
    async def start(self, tickers: list[str]) -> None:
        """Begin producing price updates for the given tickers.

        Starts a background task that periodically writes to the PriceCache.
        Must be called once, before any other method.
        """

    @abstractmethod
    async def stop(self) -> None:
        """Stop the background task. Safe to call multiple times.

        After stop() returns the source no longer writes to the cache.
        """

    @abstractmethod
    async def add_ticker(self, ticker: str) -> None:
        """Start tracking a ticker. No-op if already tracked.

        On return, the ticker has a price in the cache. Raises
        `UnknownTickerError` if the provider has no data for it.
        """

    @abstractmethod
    async def remove_ticker(self, ticker: str) -> None:
        """Stop tracking a ticker and drop it from the cache. No-op if absent."""

    @abstractmethod
    def get_tickers(self) -> list[str]:
        """Return the currently tracked tickers."""
