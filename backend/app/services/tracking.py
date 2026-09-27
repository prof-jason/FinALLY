"""Tracked tickers = watchlist ∪ open positions (PLAN §6)."""

from __future__ import annotations

import sqlite3

from app import db
from app.market import InvalidTickerError, normalize_ticker

from . import state
from .errors import ServiceError


def parse_ticker(raw: object) -> str:
    """Normalize a user-supplied ticker, raising ServiceError(400) if malformed."""
    try:
        return normalize_ticker(raw)  # type: ignore[arg-type]
    except InvalidTickerError as exc:
        raise ServiceError(str(exc), 400) from exc


def tracked_tickers(conn: sqlite3.Connection) -> list[str]:
    """Every ticker that must have live prices: watched first, then held-only."""
    tickers = [row["ticker"] for row in db.list_watchlist(conn)]
    for pos in db.list_positions(conn):
        if pos["ticker"] not in tickers:
            tickers.append(pos["ticker"])
    return tickers


def is_tracked(conn: sqlite3.Connection, ticker: str) -> bool:
    """True if the ticker is on the watchlist or held."""
    return ticker in tracked_tickers(conn)


async def untrack_if_unused(conn: sqlite3.Connection, ticker: str) -> None:
    """Stop market data for `ticker` when it is neither watched nor held."""
    if not is_tracked(conn, ticker):
        await state.get_market_source().remove_ticker(ticker)
