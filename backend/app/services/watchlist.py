"""Watchlist reads and edits, keeping the market source's tracked set in sync."""

from __future__ import annotations

from app import db
from app.market import MarketDataError, UnknownTickerError

from . import state
from .errors import ServiceError
from .tracking import parse_ticker, untrack_if_unused


def _item(ticker: str, added_at: str | None) -> dict:
    update = state.get_price_cache().get(ticker)
    return {
        "ticker": ticker,
        "price": update.price if update else None,
        "previous_price": update.previous_price if update else None,
        "change": update.change if update else None,
        "change_percent": update.change_percent if update else None,
        "direction": update.direction if update else None,
        "added_at": added_at,
    }


def get_watchlist() -> list[dict]:
    """Watched tickers in the order added, with their latest cached prices."""
    with db.get_connection() as conn:
        return [_item(row["ticker"], row["added_at"]) for row in db.list_watchlist(conn)]


async def add_watchlist_ticker(ticker: str) -> dict:
    """Add a ticker (no-op if already watched) and start tracking it.

    Raises ServiceError 400 (malformed), 404 (provider has no data) or 503.
    Nothing is written when the market source rejects the ticker.
    """
    symbol = parse_ticker(ticker)
    async with state.mutation_lock():
        try:
            await state.get_market_source().add_ticker(symbol)
        except UnknownTickerError as exc:
            raise ServiceError(str(exc), 404) from exc
        except MarketDataError as exc:
            raise ServiceError(f"Market data unavailable: {exc}", 503) from exc

        with db.get_connection() as conn:
            db.add_watchlist(conn, symbol)
            added_at = next(
                (r["added_at"] for r in db.list_watchlist(conn) if r["ticker"] == symbol), None
            )
    return _item(symbol, added_at)


async def remove_watchlist_ticker(ticker: str) -> None:
    """Remove a ticker from the watchlist; it stays tracked while a position is open.

    Raises ServiceError(404) if the ticker is not on the watchlist.
    """
    symbol = parse_ticker(ticker)
    async with state.mutation_lock():
        with db.get_connection() as conn:
            if not db.remove_watchlist(conn, symbol):
                raise ServiceError(f"{symbol} is not on the watchlist", 404)
            await untrack_if_unused(conn, symbol)
