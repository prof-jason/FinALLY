"""Ticker symbol validation and market data errors."""

from __future__ import annotations

import re

TICKER_PATTERN = re.compile(r"^[A-Z]{1,5}$")


class InvalidTickerError(ValueError):
    """Ticker symbol is malformed (maps to HTTP 400)."""


class UnknownTickerError(LookupError):
    """The data provider has no data for this ticker (maps to HTTP 404)."""

    def __init__(self, ticker: str) -> None:
        super().__init__(f"Unknown ticker: {ticker}")
        self.ticker = ticker


def normalize_ticker(raw: str) -> str:
    """Uppercase and strip a ticker, then validate it against ^[A-Z]{1,5}$."""
    if not isinstance(raw, str):
        raise InvalidTickerError(f"Invalid ticker: {raw!r}")
    ticker = raw.strip().upper()
    if not TICKER_PATTERN.fullmatch(ticker):
        raise InvalidTickerError(f"Invalid ticker: {raw!r}")
    return ticker


class MarketDataError(RuntimeError):
    """The data provider could not be reached or returned an error (maps to HTTP 503)."""
