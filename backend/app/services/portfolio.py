"""Portfolio valuation, trade execution, history and reset."""

from __future__ import annotations

import logging
import math
import sqlite3
from datetime import UTC, datetime, timedelta

from app import db

from . import state
from .errors import ServiceError
from .tracking import parse_ticker, tracked_tickers, untrack_if_unused

logger = logging.getLogger(__name__)

ZERO_EPSILON = 1e-9
SNAPSHOT_RETENTION = timedelta(days=10)


def _position_view(pos: dict) -> dict:
    """Value one position at the latest cached price (falls back to avg_cost)."""
    quantity = pos["quantity"]
    avg_cost = pos["avg_cost"]
    price = state.get_price_cache().get_price(pos["ticker"])
    current_price = price if price is not None else avg_cost
    pnl = (current_price - avg_cost) * quantity
    pnl_percent = (current_price - avg_cost) / avg_cost * 100 if avg_cost else 0.0
    return {
        "ticker": pos["ticker"],
        "quantity": quantity,
        "avg_cost": round(avg_cost, 4),
        "current_price": current_price,
        "market_value": round(current_price * quantity, 2),
        "unrealized_pnl": round(pnl, 2),
        "unrealized_pnl_percent": round(pnl_percent, 2),
    }


def _portfolio(conn: sqlite3.Connection) -> dict:
    cash = db.get_cash(conn)
    positions = [_position_view(p) for p in db.list_positions(conn)]
    invested = sum(p["market_value"] for p in positions)
    return {
        "cash_balance": round(cash, 2),
        "total_value": round(cash + invested, 2),
        "total_unrealized_pnl": round(sum(p["unrealized_pnl"] for p in positions), 2),
        "positions": positions,
    }


def get_portfolio() -> dict:
    """Cash, valued positions, total value and total unrealized P&L."""
    with db.get_connection() as conn:
        return _portfolio(conn)


def _parse_quantity(quantity: object) -> float:
    if isinstance(quantity, bool) or not isinstance(quantity, int | float | str):
        raise ServiceError("Quantity must be a number", 400)
    try:
        qty = float(quantity)
    except ValueError as exc:
        raise ServiceError("Quantity must be a number", 400) from exc
    if not math.isfinite(qty) or qty <= 0:
        raise ServiceError("Quantity must be greater than 0", 400)
    return qty


def _parse_side(side: object) -> str:
    normalized = side.strip().lower() if isinstance(side, str) else ""
    if normalized not in ("buy", "sell"):
        raise ServiceError("Side must be 'buy' or 'sell'", 400)
    return normalized


async def execute_trade(ticker: str, side: str, quantity: float) -> dict:
    """Fill a market order at the cached price; returns {"trade", "portfolio"}.

    Raises ServiceError(400) for a bad ticker/side/quantity, no cached price,
    insufficient cash or insufficient shares.
    """
    symbol = parse_ticker(ticker)
    side = _parse_side(side)
    qty = _parse_quantity(quantity)

    async with state.mutation_lock():
        price = state.get_price_cache().get_price(symbol)
        if price is None:
            raise ServiceError(f"No price available for {symbol}", 400)

        with db.get_connection() as conn:
            with db.transaction(conn):
                cash = db.get_cash(conn)
                position = db.get_position(conn, symbol)
                held = position["quantity"] if position else 0.0

                if side == "buy":
                    cost = qty * price
                    if cost > cash + ZERO_EPSILON:
                        raise ServiceError("Insufficient cash", 400)
                    new_qty = held + qty
                    old_cost = held * position["avg_cost"] if position else 0.0
                    db.upsert_position(conn, symbol, new_qty, (old_cost + cost) / new_qty)
                    db.set_cash(conn, max(cash - cost, 0.0))
                else:
                    if qty > held + ZERO_EPSILON:
                        raise ServiceError("Insufficient shares", 400)
                    remaining = held - qty
                    if abs(remaining) < ZERO_EPSILON:
                        db.delete_position(conn, symbol)
                    else:
                        db.upsert_position(conn, symbol, remaining, position["avg_cost"])
                    db.set_cash(conn, cash + qty * price)

                trade = db.insert_trade(conn, symbol, side, qty, price)
                portfolio = _portfolio(conn)
                db.insert_snapshot(conn, portfolio["total_value"])

            if side == "sell":
                await untrack_if_unused(conn, symbol)

    return {"trade": trade, "portfolio": portfolio}


def record_snapshot() -> None:
    """Record the current total value and prune snapshots past retention."""
    with db.get_connection() as conn:
        db.insert_snapshot(conn, _portfolio(conn)["total_value"])
        db.prune_snapshots(conn, datetime.now(UTC) - SNAPSHOT_RETENTION)


def get_history() -> list[dict]:
    """Snapshots from the retention window, oldest first."""
    since = datetime.now(UTC) - SNAPSHOT_RETENTION
    with db.get_connection() as conn:
        return [
            {"total_value": s["total_value"], "recorded_at": s["recorded_at"]}
            for s in db.list_snapshots(conn, since)
        ]


def get_trades(limit: int = 100) -> list[dict]:
    """Executed trades, newest first."""
    if limit < 1:
        raise ServiceError("limit must be at least 1", 400)
    with db.get_connection() as conn:
        return db.list_trades(conn, limit=limit)


async def reset_portfolio() -> dict:
    """Restore the seed state (PLAN §7) and re-sync tracked tickers."""
    source = state.get_market_source()
    async with state.mutation_lock():
        with db.get_connection() as conn:
            before = set(tracked_tickers(conn)) | set(source.get_tickers())
            with db.transaction(conn):
                db.reset_user(conn)
            after = tracked_tickers(conn)
            for ticker in after:
                try:
                    await source.add_ticker(ticker)
                except Exception:
                    logger.exception("Reset: could not track %s", ticker)
            for ticker in before - set(after):
                await source.remove_ticker(ticker)
            return _portfolio(conn)
